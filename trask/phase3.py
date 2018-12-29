# TODO: remove this
# pylint: disable=missing-docstring

import os
import shutil
import subprocess
import tempfile

import attr

from trask import functions, phase2, types


class Context:
    def __init__(self, dry_run=True):
        self.variables = {}
        self.funcs = functions.get_functions()
        self.dry_run = dry_run
        self.step = None

    def repath(self, path):
        return os.path.abspath(os.path.join(self.step.path, path))

    def resolve(self, var):
        return self.variables[var.name]

    def call(self, call):
        return self.funcs[call.name].impl(call.args)

    def run_cmd(self, *cmd):
        print(' '.join(cmd))
        if not self.dry_run:
            subprocess.check_call(cmd)


def docker_install_rust(recipe):
    lines = [
        'RUN curl -o /rustup.sh https://sh.rustup.rs', 'RUN sh /rustup.sh -y',
        'ENV PATH=$PATH:/root/.cargo/bin'
    ]
    channel = recipe.channel or 'stable'
    if channel != 'stable':
        if channel == 'nightly':
            lines.append('RUN rustup default nightly')
        else:
            raise ValueError('unknown rust channel: ' + channel)
    return lines


def docker_install_nodejs(recipe):
    nodejs_version = recipe.version
    pkg = recipe.pkg or []
    nvm_version = 'v0.33.11'
    url = ('https://raw.githubusercontent.com/' +
           'creationix/nvm/{}/install.sh'.format(nvm_version))
    return [
        'RUN curl -o- {} | bash'.format(url),
        'RUN . ~/.nvm/nvm.sh && nvm install {} && npm install -g '.format(
            nodejs_version) + ' '.join(pkg)
    ]


def create_dockerfile(recipe):
    lines = ['FROM ' + recipe.from_]
    for recipe_name, subrecipe in recipe['recipes'].items():
        if recipe_name == 'yum-install':
            lines.append('RUN yum install -y ' + ' '.join(subrecipe['pkg']))
        elif recipe_name == 'install-rust':
            lines += docker_install_rust(subrecipe)
        elif recipe_name == 'install-nodejs':
            lines += docker_install_nodejs(subrecipe)
        elif recipe_name == 'pip3-install':
            lines.append('RUN pip3 install ' + ' '.join(subrecipe['pkg']))

    lines.append('WORKDIR ' + recipe.workdir)
    return '\n'.join(lines)


def handle_docker_build(recipe, ctx):
    cmd = ['docker', 'build']
    cmd = ['sudo'] + cmd  # TODO
    tag = recipe.tag
    if tag is not None:
        cmd += ['--tag', tag]
    with tempfile.TemporaryDirectory() as temp_dir:
        dockerfile_path = os.path.join(temp_dir, 'Dockerfile')
        with open(dockerfile_path, 'w') as wfile:
            wfile.write(create_dockerfile(recipe))
        # cmd += ['--file', ctx.repath(keys['file'])]
        cmd += ['--file', dockerfile_path]
        # cmd.append(ctx.repath(keys['path']))
        cmd.append(temp_dir)
        ctx.run_cmd(*cmd)


def handle_docker_run(recipe, ctx):
    cmd = ['docker', 'run']
    cmd = ['sudo'] + cmd  # TODO
    if keys.get('init') is True:
        cmd.append('--init')
    for volume in keys.get('volumes', []):
        host = volume['host']
        container = volume['container']
        cmd += ['--volume', '{}:{}:z'.format(host, container)]
    cmd.append(keys['image'])
    cmd += ['sh', '-c', ' && '.join(keys['commands'])]
    ctx.run_cmd(*cmd)


def handle_create_temp_dir(recipe):
    var = keys['var']
    temp_dir = tempfile.TemporaryDirectory()
    # TODO
    # ctx.temp_dirs.append(temp_dir)
    ctx.variables[var] = temp_dir.name
    print('mkdir', temp_dir.name)


def handle_copy(keys):
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


def handle_upload(keys):
    identity = ctx.resolve(keys['identity'])
    user = ctx.resolve(keys['user'])
    host = ctx.resolve(keys['host'])
    src = ctx.resolve(keys['src'])
    dst = ctx.resolve(keys['dst'])
    replace = ctx.resolve(keys.get('replace', False))
    target = '{}@{}'.format(user, host)

    if replace is True:
        run_cmd('ssh', '-i', identity, target, 'rm', '-fr', dst)

    run_cmd('scp', '-i', identity, '-r', src, '{}:{}'.format(target, dst))


def handle_set(recipe, ctx):
    dct = attr.asdict(recipe)
    for key, val in dct.items():
        ctx.variables[key] = val


def handle_ssh(recipe, ctx):
    target = '{}@{}'.format(recipe.user, recipe.host)
    command = ' && '.join(recipe.commands)
    ctx.run_cmd('ssh', '-i', recipe.identity, target, command)


def resolve_value(val, ctx):
    result = None
    if val.data is None:
        result = None
    elif isinstance(val.data, (bool, str)):
        result = val.data
    elif isinstance(val.data, types.Var):
        result = ctx.resolve(val.data)
        if val.data.choices is not None:
            if result not in val.data.choices:
                raise phase2.InvalidChoice(result)
    elif isinstance(val.data, types.Call):
        result = ctx.call(val.data)
    else:
        raise TypeError('invalid value type')

    if val.is_path is True:
        result = ctx.repath(result)
    return result


def resolve(val, ctx):
    if isinstance(val, types.Value):
        return resolve_value(val, ctx)
    elif isinstance(val, list):
        lst = []
        for elem in val:
            lst.append(resolve(elem, ctx))
        return lst
    else:
        dct = attr.asdict(val, recurse=False)
        for key, subval in dct.items():
            setattr(val, key, resolve(subval, ctx))
        return val


def resolve_step(step, ctx):
    recipe = resolve(step.recipe, ctx)
    return types.Step(step.name, recipe, step.path)


HANDLERS = {
    'copy': handle_copy,
    'create-temp-dir': handle_create_temp_dir,
    'docker-build': handle_docker_build,
    'docker-run': handle_docker_run,
    'set': handle_set,
    'ssh': handle_ssh,
    'upload': handle_upload,
}


def run(steps, ctx):
    for step in steps:
        rstep = resolve_step(step, ctx)
        ctx.step = rstep
        HANDLERS[rstep.name](rstep.recipe, ctx)
