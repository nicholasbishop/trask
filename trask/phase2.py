# TODO: remove this
# pylint: disable=missing-docstring

import collections
import keyword
import os

import attr
import tatsu

from trask import functions, types

GRAMMAR = '''
  @@grammar::TraskSchema
  @@eol_comments :: /#.*?$/
  top = { step } $ ;
  step = name:ident recipe:dictionary ;
  dictionary = '{' @:{ pair } '}' ;
  pair = key:key ':' type:type ';' ;
  key = required:[ "required" ] name:(ident | "*" ) ;
  type = inner:( primitive | dictionary ) array:[ "[]" ] choices:[ choices ];
  choices = "choices" "(" ","%{ @:string } ")" ;
  primitive = "path" | "string" | "bool" | "any" ;
  boolean = "true" | "false" ;
  string = "'" @:/[^']*/ "'" ;
  ident = /[a-zA-Z0-9_-]+/ ;
'''


@attr.s(frozen=True)
class Key:
    name = attr.ib()
    is_required = attr.ib(default=False, cmp=False, hash=False)


def make_keys_safe(dct):
    """Modify the keys in |dct| to be valid attribute names."""
    result = {}
    for key, val in dct.items():
        key = key.replace('-', '_')
        if key in keyword.kwlist:
            key = key + '_'
        result[key] = val
    return result


class SchemaError(ValueError):
    pass


class MissingKey(SchemaError):
    pass


class InvalidKey(SchemaError):
    pass


class TypeMismatch(SchemaError):
    pass


class InvalidChoice(SchemaError):
    pass


class UnboundVariable(SchemaError):
    pass


class InvalidFunction(SchemaError):
    pass


def does_substition_match(type1, type2):
    path_types = (types.Kind.String, types.Kind.Path)
    return ((type1 == type2) or (type1 in path_types and type2 in path_types)
            or type1 == types.Kind.Any or type2 == types.Kind.Any)


@attr.s(init=False)
class Phase2:
    step = attr.ib()
    variables = attr.ib()
    functions = attr.ib()

    def __init__(self):
        self.step = None
        self.variables = {}
        self.functions = functions.get_functions()

    def load_any(self, _, val, path):
        # pylint: disable=no-self-use
        if val is None:
            raise TypeMismatch(path)
        return types.Value(val)

    def load_bool(self, _, val, path):
        # pylint: disable=no-self-use
        if not isinstance(val, bool):
            raise TypeMismatch(path)
        return types.Value(val)

    def load_string(self, _, val, path):
        # pylint: disable=no-self-use
        if not isinstance(val, str):
            raise TypeMismatch(path)
        return types.Value(val)

    def load_path(self, _, val, path):
        # pylint: disable=no-self-use
        if not isinstance(val, str):
            raise TypeMismatch(path)
        return types.Value(val, is_path=True)

    def load_array(self, schema, val, path):
        if not isinstance(val, list):
            raise TypeMismatch(path)
        lst = []
        for index, elem in enumerate(val):
            subpath = path + [index]
            lst.append(self.load_one(schema.array_type, elem, subpath))
        return lst

    def load_step(self, schema, val, path):
        self.step = val
        fields = self.load_one(schema.fields[Key(val.name)], val.recipe,
                               path + [val.name])
        # TODO, might be better to encode this in the schema somehow
        if val.name == 'create-temp-dir':
            self.variables[fields.var.data] = types.Kind.Path
        elif val.name == 'set':
            for key in val.recipe:
                if isinstance(val.recipe[key], str):
                    self.variables[key] = types.Kind.String
                elif isinstance(val.recipe[key], bool):
                    self.variables[key] = types.Kind.Bool
                elif isinstance(val.recipe[key], types.Call):
                    self.variables[key] = self.functions[val.recipe[key].
                                                         name].return_type
                else:
                    raise SchemaError('invalid variable type')
        return types.Step(val.name, fields, val.path)

    def load_object(self, schema, val, path):
        if isinstance(val, types.Step):
            return self.load_step(schema, val, path)
        else:
            if not isinstance(val, collections.abc.Mapping):
                raise TypeMismatch(path)
            temp_obj = {}
            if schema.wildcard_key():
                for key in val:
                    subpath = path + [key]
                    temp_obj[key] = self.load_one(schema.fields[Key('*')],
                                                  val[key], subpath)
            else:
                for key in val:
                    if Key(key) not in schema.fields:
                        raise InvalidKey(path, key)
                    subpath = path + [key]
                    temp_obj[key] = self.load_one(schema.fields[Key(key)],
                                                  val[key], subpath)
            for key in schema.fields:
                if key.name not in temp_obj and key.name != '*':
                    temp_obj[key.name] = types.Value(None)
                if key.is_required:
                    if key.name not in val:
                        raise MissingKey(path)
            temp_obj = make_keys_safe(temp_obj)
            cls = attr.make_class('SchemaClass', list(temp_obj.keys()))
            return cls(**temp_obj)

    def load_one(self, schema, val, path):
        is_path = schema.kind == types.Kind.Path
        if isinstance(val, types.Var):
            if val.name not in self.variables:
                raise UnboundVariable(path)
            elif not does_substition_match(self.variables[val.name],
                                           schema.kind):
                raise TypeMismatch(path)

            return types.Value(
                types.Var(val.name, choices=schema.choices), is_path)
        elif isinstance(val, types.Call):
            if val.name not in self.functions:
                raise InvalidFunction(path)
            elif not does_substition_match(
                    self.functions[val.name].return_type, schema.kind):

                raise TypeMismatch(path)

            return types.Value(types.Call(val.name, val.args), is_path)
        else:
            result = {
                types.Kind.Any: self.load_any,
                types.Kind.Bool: self.load_bool,
                types.Kind.String: self.load_string,
                types.Kind.Path: self.load_path,
                types.Kind.Array: self.load_array,
                types.Kind.Object: self.load_object,
            }[schema.kind](schema, val, path)

            if schema.choices is not None:
                if result.data not in schema.choices:
                    raise InvalidChoice()

            return result

    @classmethod
    def load(cls, schema, val, variables=None):
        loader = cls()
        if variables is not None:
            loader.variables = variables
        return loader.load_one(schema, val, [])


@attr.s
class Type:
    kind = attr.ib()
    array_type = attr.ib(default=None)
    choices = attr.ib(default=None)
    fields = attr.ib(default=None)

    def wildcard_key(self):
        if self.kind == types.Kind.Object:
            for key in self.fields:
                if key.name == '*':
                    return True
        return False


class Semantics:
    # pylint: disable=no-self-use

    def key(self, ast):
        is_required = ast['required'] is not None
        return Key(name=ast['name'], is_required=is_required)

    def top(self, ast):
        return Type(
            kind=types.Kind.Array,
            array_type=Type(
                kind=types.Kind.Object,
                fields=dict(
                    (Key(pair['name']), pair['recipe']) for pair in ast)))

    def dictionary(self, ast):
        return Type(
            kind=types.Kind.Object,
            fields=dict((pair['key'], pair['type']) for pair in ast))

    def primitive(self, ast):
        if ast == 'path':
            return Type(kind=types.Kind.Path)
        elif ast == 'string':
            return Type(kind=types.Kind.String)
        elif ast == 'bool':
            return Type(kind=types.Kind.Bool)
        elif ast == 'any':
            return Type(kind=types.Kind.Any)
        else:
            raise ValueError('invalid primitive')

    def type(self, ast):
        inner = ast['inner']
        choices = choices = ast['choices']
        if ast['array']:
            return Type(
                kind=types.Kind.Array,
                array_type=inner,
                fields=None,
                choices=choices)
        else:
            inner.choices = choices
            return inner


MODEL = tatsu.compile(GRAMMAR, semantics=Semantics())

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(SCRIPT_DIR, 'schema')) as rfile:
    SCHEMA = MODEL.parse(rfile.read())
