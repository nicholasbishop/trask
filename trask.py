#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import tempfile

import tatsu

GRAMMAR = '''
  @@grammar::Trask
  @@eol_comments :: /#.*?$/
  top = { step } $ ;
  step = name:ident dictionary:dictionary ;
  dictionary = '{' @:{ pair } '}' ;
  pair = key:ident ':' value:value ;
  value = dictionary | call | boolean | var | string ;
  call = func:ident '(' args:{value} ')' ;
  boolean = "true" | "false" ;
  string = "'" @:/[^']*/ "'" ;
  var = ident ;
  ident = /[a-zA-Z_-]+/ ;
'''


class Var:
    def __init__(self, name):
        self.name = name


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

    def var(self, ast):
        return Var(ast)


MODEL = tatsu.compile(GRAMMAR, semantics=Semantics())


def run_cmd(*cmd):
    print(' '.join(cmd))
    subprocess.check_call(cmd)


class Context:
    def __init__(self, trask_file):
        self.trask_file = trask_file
        self.variables = {}
        self.temp_dirs = []

    def repath(self, path):
        return os.path.abspath(
            os.path.join(os.path.dirname(self.trask_file), path))

    def resolve(self, var):
        if isinstance(var, Var):
            return self.variables[var.name]
        return var


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

    def get_all(self, key):
        return self.pairs[key]


def handle_docker_build(ctx, keys):
    cmd = ['docker', 'build']
    if keys.get('sudo') is True:
        cmd = ['sudo'] + cmd
    tag = keys.get('tag')
    if tag is not None:
        cmd += ['--tag', tag]
    cmd += ['--file', ctx.repath(keys['file'])]
    cmd.append(ctx.repath(keys['path']))
    run_cmd(*cmd)


def handle_docker_run(ctx, keys):
    cmd = ['docker', 'run']
    if keys.get('sudo') is True:
        cmd = ['sudo'] + cmd
    if keys.get('init') is True:
        cmd.append('--init')
    for volume in keys.get_all('volume'):
        host = ctx.repath(volume['host'])
        container = volume['container']
        cmd += ['--volume', '{}:{}'.format(host, container)]
    cmd.append(keys['image'])
    cmd.append(keys['command'])
    run_cmd(*cmd)


def handle_create_temp_dir(ctx, keys):
    var = keys['var']
    temp_dir = tempfile.TemporaryDirectory()
    ctx.temp_dirs.append(temp_dir)
    ctx.variables[var] = temp_dir.name
    print('mkdir', temp_dir.name)


def handle_copy(ctx, keys):
    dst = ctx.resolve(keys['dst'])
    for src in keys.get_all('src'):
        src = ctx.resolve(src)
        src = ctx.repath(src)
        if os.path.isdir(src):
            newdir = os.path.join(dst, os.path.basename(src))
            print('copy', src, newdir)
            shutil.copytree(src, newdir)
        else:
            print('copy', src, dst)
            shutil.copy2(src, dst)


def main():
    parser = argparse.ArgumentParser(description='run a trask file')
    parser.add_argument('path')
    args = parser.parse_args()

    with open(args.path) as rfile:
        steps = MODEL.parse(rfile.read())

    ctx = Context(args.path)

    handlers = {
        'docker-build': handle_docker_build,
        'docker-run': handle_docker_run,
        'create-temp-dir': handle_create_temp_dir,
        'copy': handle_copy,
        'scp': handle_scp,
    }

    for step in steps:
        handlers[step['name']](ctx, step['dictionary'])


if __name__ == '__main__':
    main()
