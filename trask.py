#!/usr/bin/env python3

# TODO: remove this
# pylint: disable=missing-docstring

import argparse
import os
import shutil
import subprocess
import tempfile

import attr
import tatsu

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


class Var:
    def __init__(self, name):
        self.name = name


@attr.s
class Call:
    name = attr.ib()
    args = attr.ib()


class Semantics:
    # pylint: disable=no-self-use
    def boolean(self, ast):
        if ast == 'true':
            return True
        elif ast == 'false':
            return False
        else:
            raise ValueError(ast)

    def dictionary(self, ast):
        return dict((pair['key'], pair['value']) for pair in ast)

    def var(self, ast):
        return Var(ast)

    def call(self, ast):
        return Call(ast['func'], ast['args'])


MODEL = tatsu.compile(GRAMMAR, semantics=Semantics())


def run_cmd(*cmd):
    print(' '.join(cmd))
    subprocess.check_call(cmd)


def get_from_env(_, args):
    key = args[0]
    return os.environ[key]


class Context:
    def __init__(self, trask_file):
        self.trask_file = trask_file
        self.variables = {}
        self.temp_dirs = []
        self.funcs = {'env': get_from_env}

    def repath(self, path):
        return os.path.abspath(
            os.path.join(os.path.dirname(self.trask_file), path))

    def resolve(self, val):
        if isinstance(val, Var):
            return self.variables[val.name]
        elif isinstance(val, Call):
            return self.funcs[val.name](self, val.args)
        return val


def docker_install_rust(recipe):
    lines = [
        'RUN curl -o /rustup.sh https://sh.rustup.rs',
        'RUN sh /rustup.sh -y', 'ENV PATH=$PATH:/root/.cargo/bin'
    ]
    channel = recipe.get('channel', 'stable')
    if channel != 'stable':
        if channel == 'nightly':
            lines.append('RUN rustup default nightly')
        else:
            raise ValueError('unknown rust channel: ' + channel)
    return lines


def create_dockerfile(obj):
    lines = ['FROM ' + obj['from']]
    for recipe_name, recipe in obj['recipes'].items():
        if recipe_name == 'yum-install':
            lines.append('RUN yum install -y ' + ' '.join(recipe['pkg']))
        elif recipe_name == 'install-rust':
            lines += docker_install_rust(recipe)
        elif recipe_name == 'install-nodejs':
            nodejs_version = recipe['version']
            nvm_version = 'v0.33.11'
            url = ('https://raw.githubusercontent.com/' +
                   'creationix/nvm/{}/install.sh'.format(nvm_version))
            lines += [
                'RUN curl -o- {} | bash'.format(url),
                'RUN . ~/.nvm/nvm.sh && nvm install {} && npm install -g '.
                format(nodejs_version) + ' '.join(recipe.get('pkg'))
            ]

    lines.append('WORKDIR ' + obj['workdir'])
    return '\n'.join(lines)


def handle_docker_build(ctx, keys):
    cmd = ['docker', 'build']
    cmd = ['sudo'] + cmd  # TODO
    tag = ctx.resolve(keys.get('tag'))
    if tag is not None:
        cmd += ['--tag', tag]
    with tempfile.TemporaryDirectory() as temp_dir:
        dockerfile_path = os.path.join(temp_dir, 'Dockerfile')
        with open(dockerfile_path, 'w') as wfile:
            wfile.write(create_dockerfile(keys))
            print(create_dockerfile(keys))
        # cmd += ['--file', ctx.repath(keys['file'])]
        cmd += ['--file', dockerfile_path]
        # cmd.append(ctx.repath(keys['path']))
        cmd.append(temp_dir)
        run_cmd(*cmd)


def handle_docker_run(ctx, keys):
    cmd = ['docker', 'run']
    cmd = ['sudo'] + cmd  # TODO
    if keys.get('init') is True:
        cmd.append('--init')
    for volume in keys.get('volumes', []):
        host = ctx.repath(volume['host'])
        container = volume['container']
        cmd += ['--volume', '{}:{}'.format(host, container)]
    cmd.append(keys['image'])
    cmd += ['sh', '-c', ' && '.join(keys['commands'])]
    run_cmd(*cmd)


def handle_create_temp_dir(ctx, keys):
    var = keys['var']
    temp_dir = tempfile.TemporaryDirectory()
    ctx.temp_dirs.append(temp_dir)
    ctx.variables[var] = temp_dir.name
    print('mkdir', temp_dir.name)


def handle_copy(ctx, keys):
    dst = ctx.resolve(keys['dst'])
    for src in keys['src']:
        src = ctx.resolve(src)
        src = ctx.repath(src)
        if os.path.isdir(src):
            newdir = os.path.join(dst, os.path.basename(src))
            print('copy', src, newdir)
            shutil.copytree(src, newdir)
        else:
            print('copy', src, dst)
            shutil.copy2(src, dst)


def handle_upload(ctx, keys):
    identity = ctx.resolve(keys['identity'])
    user = ctx.resolve(keys['user'])
    host = ctx.resolve(keys['host'])
    src = ctx.resolve(keys['src'])
    dst = ctx.resolve(keys['dst'])
    replace = ctx.resolve(keys.get('replace', False))
    target = '{}@{}'.format(user, host)

    if replace is True:
        run_cmd('ssh', '-i', identity, target, 'rm', '-r', dst)

    run_cmd('scp', '-i', identity, '-r', src, '{}:{}'.format(target, dst))


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
        'upload': handle_upload,
    }

    for step in steps:
        handlers[step['name']](ctx, step['recipe'])


if __name__ == '__main__':
    main()
