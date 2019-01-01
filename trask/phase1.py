# TODO: remove this
# pylint: disable=missing-docstring

import collections
import os

import tatsu

from trask import types

GRAMMAR = '''
  @@grammar::Trask
  @@eol_comments :: /#.*?$/
  top = { step } $ ;
  step = name:ident recipe:dictionary ;
  dictionary = '{' @:{ pair } '}' ;
  list = '[' @:{ value } ']' ;
  pair = key:ident value:value ;
  value = dictionary | list | call | boolean | var | string ;
  call = func:ident '(' args:{value} ')' ;
  boolean = "true" | "false" ;
  string = "'" @:/[^']*/ "'" ;
  var = ident ;
  ident = /[a-zA-Z0-9_-]+/ ;
'''


class Semantics:
    # pylint: disable=no-self-use
    def boolean(self, ast):
        if ast == 'true':
            return True
        elif ast == 'false':
            return False
        else:
            raise ValueError(ast)

    def step(self, ast):
        return types.Step(ast.name, ast.recipe, None)

    def dictionary(self, ast):
        return collections.OrderedDict(
            (pair['key'], pair['value']) for pair in ast)

    def var(self, ast):
        return types.Var(ast)

    def call(self, ast):
        return types.Call(ast['func'], ast['args'])


MODEL = tatsu.compile(GRAMMAR, semantics=Semantics())


def expand_includes(step, path):
    if step.name == 'include' and 'file' in step.recipe:
        rel_path = step.recipe['file']
        if isinstance(rel_path, types.Var):
            raise TypeError('include path cannot be a variable')
        dirname = os.path.dirname(path)
        new_path = os.path.abspath(os.path.join(dirname, rel_path))
        return load(new_path)
    else:
        step.path = path
        return [step]


def load(path):
    """Load |path| and recursively expand any includes."""
    with open(path) as rfile:
        steps = MODEL.parse(rfile.read())

    new_steps = []
    for step in steps:
        new_steps += expand_includes(step, path)

    return new_steps
