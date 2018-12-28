import collections
import keyword
import os

import attr
import tatsu

from trask import types

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
  primitive = "path" | "string" | "bool" ;
  boolean = "true" | "false" ;
  string = "'" @:/[^']*/ "'" ;
  ident = /[a-zA-Z0-9_-]+/ ;
'''


class Kind:
    Bool = 'bool'
    String = 'string'
    Path = 'path'
    Array = 'array'
    Object = 'object'


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


@attr.s
class Phase2:
    step = attr.ib()
    variables = attr.ib()

    def load_bool(self, schema, val, path):
        if not isinstance(val, bool):
            raise TypeMismatch(path)
        return val

    def load_string(self, schema, val, path):
        if not isinstance(val, str):
            raise TypeMismatch(path)
        return val

    def load_path(self, schema, val, path):
        if not isinstance(val, str):
            raise TypeMismatch(path)
        return os.path.abspath(os.path.join(self.step.path, val))

    def load_array(self, schema, val, path):
        if not isinstance(val, list):
            raise TypeMismatch(path)
        lst = []
        for index, elem in enumerate(val):
            subpath = path + [index]
            lst.append(self.load_any(schema.array_type, elem, subpath))
        return lst

    def load_object(self, schema, val, path):
        if isinstance(val, types.Step):
            self.step = val
            fields = self.load_any(schema.fields[Key(val.name)],
                                   val.recipe, path + [val.name])
            return types.Step(val.name, fields, val.path)
        else:
            if not isinstance(val, collections.abc.Mapping):
                raise TypeMismatch(path)
            temp_obj = {}
            if schema.wildcard_key():
                for key in val:
                    subpath = path + [key]
                    temp_obj[key] = self.load_any(schema.fields[Key('*')],
                                                  val[key], subpath)
            else:
                for key in val:
                    if Key(key) not in schema.fields:
                        raise InvalidKey(path, key)
                    subpath = path + [key]
                    temp_obj[key] = self.load_any(schema.fields[Key(key)],
                                                  val[key], subpath)
            for key in schema.fields:
                if key.name not in temp_obj and key.name != '*':
                    temp_obj[key.name] = None
                if key.is_required:
                    if key.name not in val:
                        raise MissingKey(path)
            temp_obj = make_keys_safe(temp_obj)
            cls = attr.make_class('SchemaClass', list(temp_obj.keys()))
            return cls(**temp_obj)

    def load_any(self, schema, val, path):
        if isinstance(val, types.Var):
            if val.name not in self.variables:
                raise UnboundVariable(path)
            elif self.variables[val.name] != schema.kind:
                raise TypeMismatch(path)

            return types.Var(val.name, choices=schema.choices)
        else:
            result = {
                Kind.Bool: self.load_bool,
                Kind.String: self.load_string,
                Kind.Path: self.load_path,
                Kind.Array: self.load_array,
                Kind.Object: self.load_object,
            }[schema.kind](schema, val, path)

            if schema.choices is not None:
                if result not in schema.choices:
                    raise InvalidChoice()

            return result
        
    @classmethod
    def load(cls, schema, val):
        phase2 = cls(step=None, variables={})
        return phase2.load_any(schema, val, [])


@attr.s
class Type:
    kind = attr.ib()
    array_type = attr.ib(default=None)
    choices = attr.ib(default=None)
    fields = attr.ib(default=None)

    def wildcard_key(self):
        if self.kind == Kind.Object:
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
            kind=Kind.Array,
            array_type=Type(
                kind=Kind.Object,
                fields=dict(
                    (Key(pair['name']), pair['recipe']) for pair in ast)))

    def dictionary(self, ast):
        return Type(
            kind=Kind.Object,
            fields=dict((pair['key'], pair['type']) for pair in ast))

    def primitive(self, ast):
        if ast == 'path':
            return Type(kind=Kind.Path)
        elif ast == 'string':
            return Type(kind=Kind.String)
        elif ast == 'bool':
            return Type(kind=Kind.Bool)

    def type(self, ast):
        inner = ast['inner']
        is_array = ast['array'] or False
        choices = choices = ast['choices']
        fields = None
        array_type = None
        if ast['array']:
            kind = Kind.Array
            array_type = inner
        elif isinstance(inner, Type):
            inner.choices = choices
            return inner
        return Type(
            kind=kind, array_type=array_type, fields=fields, choices=choices)


MODEL = tatsu.compile(GRAMMAR, semantics=Semantics())

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(SCRIPT_DIR, 'schema')) as rfile:
    SCHEMA = MODEL.parse(rfile.read())


