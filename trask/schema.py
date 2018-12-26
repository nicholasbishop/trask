import collections
import os

import attr
import tatsu

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


@attr.s
class Type:
    kind = attr.ib()
    array_type = attr.ib(default=None)
    choices = attr.ib(default=None)
    fields = attr.ib(default=None)

    def validate(self, val, path=None):
        if path is None:
            path = []

        if self.kind == Kind.Bool:
            if not isinstance(val, bool):
                raise TypeMismatch(path)
        elif self.kind == Kind.String:
            if not isinstance(val, str):
                raise TypeMismatch(path)
        elif self.kind == Kind.Path:
            if not isinstance(val, str):
                raise TypeMismatch(path)
        elif self.kind == Kind.Array:
            if not isinstance(val, list):
                raise TypeMismatch(path)
            for index, elem in enumerate(val):
                self.array_type.validate(elem, path + [index])
        elif self.kind == Kind.Object:
            if not isinstance(val, collections.abc.Mapping):
                raise TypeMismatch(path)
            if not self.wildcard_key():
                for key in val:
                    if Key(key) not in self.fields:
                        raise InvalidKey(path, key)
                    self.fields[Key(key)].validate(val[key], path + [key])
            for key in self.fields:
                if key.is_required:
                    if key.name not in val:
                        raise MissingKey(path)

        if self.choices is not None:
            if val not in self.choices:
                raise InvalidChoice()

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
