#!/usr/bin/env python3

import argparse
import os
import subprocess

import tatsu

GRAMMAR = '''
  @@grammar::Trask
  @@eol_comments :: /#.*?$/
  top = { step } $ ;
  step = name:ident dictionary:dictionary ;
  dictionary = '{' @:{ pair } '}' ;
  pair = key:ident ':' value:value ;
  value = dictionary | call | boolean | ident | string ;
  call = func:ident '(' args:{value} ')' ;
  boolean = "true" | "false" ;
  string = "'" @:/[^']*/ "'" ;
  ident = /[a-zA-Z_-]+/ ;
'''

SCHEMA = {
    'docker-build': {
        'sudo': {
            'type': 'boolean',
            'required': False,
            'count': '?',
        },
        'tag': {
            'type': 'string',
            'count': 1
        },
        'file': {
            'type': 'path',
            'count': 1
        },
        'path': {
            'type': 'path',
            'count': 1
        }
    },
    'docker-run': {
        'sudo': {
            'type': 'boolean',
            'count': '?',
            'default': False,
        },
        'image': {
            'type': 'string',
            'count': 1,
        },
        'init': {
            'type': 'boolean',
            'count': '?',
            'default': False
        },
        'volume': {
            'type': 'dictionary',
            'count': '*',
            'keys': {
                'host': {
                    'type': 'string',
                    'count': 1,
                },
                'container': {
                    'type': 'string',
                    'count': 1
                }
            }
        },
        'command': {
            'type': 'string',
            'count': 1,
        }
    }
}


class Semantics:
    def boolean(self, ast):
        if ast == 'true':
            return True
        elif ast == 'false':
            return False
        else:
            raise ValueError(ast)

    def dictionary(self, ast):
        return Dictionary(ast)


MODEL = tatsu.compile(GRAMMAR, semantics=Semantics())


def run_cmd(*cmd):
    print(' '.join(cmd))
    subprocess.check_call(cmd)


class Context:
    def __init__(self, trask_file):
        self.trask_file = trask_file
        self.variables = {}

    def repath(self, path):
        return os.path.join(os.path.dirname(self.trask_file), path)


class Dictionary:
    def __init__(self, pairs):
        self.pairs = {}
        for pair in pairs:
            key = pair['key']
            value = pair['value']
            if key not in self.pairs:
                self.pairs[key] = []
            self.pairs[key].append(value)

    def get(self, key):
        if key not in self.pairs:
            return None
        values = self.pairs.get(key, [])
        if len(values) == 1:
            return values[0]
        else:
            raise KeyError('multiple values for key', key)

    def __getitem__(self, key):
        if key not in self.pairs:
            raise KeyError('missing key', key)
        return self.get(key)


def validate_array(array, schema):
    count = schema.get('count', 1)
    elem_type = schema['type']

    if count == '?' and len(array) not in (0, 1):
        raise ValueError('expected zero or one elements')
    elif count == '+' and len(array) < 1:
        raise ValueError('expected one or more elements')
    elif len(array) != count:
        raise ValueError('expected {} elements'.format(count))

    for elem in array:
        if elem_type == 'boolean':
            if not isinstance(elem, bool):
                raise TypeError('value is not a boolean')
        elif elem_type == 'dictionary':
            if not isinstance(elem, dict):
                raise TypeError('value is not a dictionary')
            for key in elem:
                validate_array(elem[key], schema['keys'][key])
        else:
            raise ValueError('invalid type name in schema')


def handle_docker_build(ctx, keys):
    print(keys.pairs)
    cmd = ['docker', 'build']
    if keys.get('sudo') is True:
        cmd = ['sudo'] + cmd
    tag = keys.get('tag')
    if tag is not None:
        cmd += ['--tag', tag]
    cmd += ['--file', ctx.repath(keys['file'])]
    cmd.append(ctx.repath(keys['path']))
    run_cmd(*cmd)


def main():
    parser = argparse.ArgumentParser(description='run a trask file')
    parser.add_argument('path')
    args = parser.parse_args()

    with open(args.path) as rfile:
        steps = MODEL.parse(rfile.read())

    ctx = Context(args.path)

    handlers = {
        'docker-build': handle_docker_build
    }

    for step in steps:
        handlers[step['name']](ctx, step['map'])


if __name__ == '__main__':
    main()
