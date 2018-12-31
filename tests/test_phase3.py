# pylint: disable=missing-docstring

import os
import unittest
from unittest import mock

import attr
from pyfakefs import fake_filesystem_unittest

from trask import phase2, phase3, types


class TestResolveValue(unittest.TestCase):
    def test_none(self):
        self.assertIs(phase3.resolve_value(types.Value(None), None), None)

    def test_bool(self):
        self.assertEqual(phase3.resolve_value(types.Value(True), None), True)
        self.assertEqual(phase3.resolve_value(types.Value(False), None), False)

    def test_string(self):
        self.assertEqual(phase3.resolve_value(types.Value('foo'), None), 'foo')

    def test_path(self):
        class Context:
            def repath(self, path):
                # pylint: disable=no-self-use
                return os.path.join('/root', path)

        self.assertEqual(
            phase3.resolve_value(types.Value('foo', is_path=True), Context()),
            '/root/foo')

    def test_var(self):
        this = self

        class Context:
            def resolve(self, var):
                # pylint: disable=no-self-use
                this.assertEqual(var.name, 'foo')
                return 'myResult'

        self.assertEqual(
            phase3.resolve_value(types.Value(types.Var('foo')), Context()),
            'myResult')

    def test_var_choices(self):
        class Context:
            def resolve(self, _):
                # pylint: disable=no-self-use
                return 'z'

        self.assertEqual(
            phase3.resolve_value(
                types.Value(types.Var('foo', choices=('x', 'z'))), Context()),
            'z')
        with self.assertRaises(phase2.InvalidChoice):
            phase3.resolve_value(
                types.Value(types.Var('foo', choices=('x', 'y'))), Context())

    def test_call(self):
        this = self

        class Context:
            def call(self, call):
                # pylint: disable=no-self-use
                this.assertEqual(call.name, 'foo')
                return 'myResult'

        self.assertEqual(
            phase3.resolve_value(
                types.Value(types.Call('foo', ())), Context()), 'myResult')

    def test_invalid_value(self):
        with self.assertRaises(TypeError):
            phase3.resolve_value(types.Value(object()), None)


class TestResolve(unittest.TestCase):
    def test_primitive(self):
        self.assertEqual(phase3.resolve(types.Value(True), None), True)
        self.assertEqual(phase3.resolve(types.Value('foo'), None), 'foo')

    def test_var(self):
        ctx = phase3.Context()
        ctx.variables['foo'] = 'bar'
        self.assertEqual(
            phase3.resolve(types.Value(types.Var('foo')), ctx), 'bar')

    def test_call(self):
        ctx = phase3.Context()
        os.environ['FOO'] = 'bar'
        call = types.Call('env', ('FOO', ))
        self.assertEqual(phase3.resolve(types.Value(call), ctx), 'bar')

    def test_list(self):
        lst = [types.Value('x'), types.Value('y')]
        self.assertEqual(phase3.resolve(lst, None), ['x', 'y'])

    def test_object(self):
        cls = attr.make_class('Mock', ['foo'])
        obj = cls(types.Value('bar'))
        obj = phase3.resolve(obj, None)
        self.assertEqual(obj.foo, 'bar')

    def test_step(self):
        # pylint: disable=no-self-use
        cls = attr.make_class('MockRecipe', ())
        recipe = cls()
        step = types.Step('foo', recipe, None)
        phase3.resolve_step(step, None)

    def test_repath(self):
        ctx = phase3.Context()
        ctx.step = types.Step('foo', None, '/base')
        self.assertEqual(ctx.repath('myPath'), '/base/myPath')


def context_command_recorder():
    ctx = phase3.Context()
    ctx.commands = []

    def run_cmd(self, *cmd):
        self.commands.append(cmd)

    # pylint: disable=assignment-from-no-return
    ctx.run_cmd = run_cmd.__get__(ctx, phase3.Context)
    return ctx


class TestPhase3(unittest.TestCase):
    def test_handlers(self):
        """Check that all of the steps in the schema have handlers."""
        step_names = set()
        for step in phase2.SCHEMA.array_type.fields:
            step_names.add(step.name)

        # Includes are expanded in phase1
        step_names.remove('include')

        self.assertEqual(step_names, phase3.HANDLERS.keys())

    def test_run_cmd(self):
        # pylint: disable=no-self-use
        ctx = phase3.Context(dry_run=False)
        ctx.run_cmd('true')
        ctx.dry_run = True
        ctx.run_cmd('false')

    def test_set(self):
        cls = attr.make_class('SetMock', ['foo'])
        obj = cls('bar')
        ctx = phase3.Context()
        phase3.handle_set(obj, ctx)
        self.assertEqual(ctx.variables, {'foo': 'bar'})

    def test_handle_ssh(self):
        cls = attr.make_class('Mock', ['identity', 'user', 'host', 'commands'])
        obj = cls(
            identity='/myId', user='me', host='myHost', commands=['a', 'b'])

        ctx = context_command_recorder()

        phase3.handle_ssh(obj, ctx)
        self.assertEqual(ctx.commands,
                         [('ssh', '-i', '/myId', 'me@myHost', 'a && b')])

    def test_handle_update(self):
        cls = attr.make_class(
            'Mock', ['user', 'host', 'identity', 'replace', 'src', 'dst'])
        obj = cls(
            user='me',
            host='myHost',
            identity='/myId',
            replace=False,
            src='/src',
            dst='/dst')

        ctx = context_command_recorder()

        phase3.handle_upload(obj, ctx)
        self.assertEqual(
            ctx.commands,
            [('scp', '-i', '/myId', '-r', '/src', 'me@myHost:/dst')])

        obj.replace = True
        ctx.commands = []
        phase3.handle_upload(obj, ctx)
        self.assertEqual(
            ctx.commands,
            [('ssh', '-i', '/myId', 'me@myHost', 'rm', '-fr', '/dst'),
             ('scp', '-i', '/myId', '-r', '/src', 'me@myHost:/dst')])

    def test_run(self):
        cls = attr.make_class('MockSet', ['a'])
        recipe = cls(types.Value('b'))
        steps = [types.Step('set', recipe, None)]
        ctx = phase3.Context()
        phase3.run(steps, ctx)
        self.assertEqual(ctx.variables, {'a': 'b'})


class TestDocker(unittest.TestCase):
    def test_yum_install(self):
        cls = attr.make_class('YumInstall', ['pkg'])
        obj = cls(['a', 'b'])

        lines = phase3.docker_yum_install(obj)
        self.assertEqual(lines, 'RUN yum install -y a b')

    def test_rust(self):
        obj = attr.make_class('Mock', ['channel'])(None)
        obj.channel = None
        lines1 = phase3.docker_install_rust(obj)
        obj.channel = 'stable'
        lines2 = phase3.docker_install_rust(obj)
        obj.channel = 'nightly'
        lines3 = phase3.docker_install_rust(obj)
        self.assertEqual(lines1, lines2)
        self.assertEqual(len(lines1) + 1, len(lines3))
        with self.assertRaises(ValueError):
            obj.channel = 'badChannel'
            phase3.docker_install_rust(obj)

    def test_install_nodejs(self):
        cls = attr.make_class('Mock', ['pkg', 'version'])
        obj = cls(version='1.2.3', pkg=None)
        lines = phase3.docker_install_nodejs(obj)
        self.assertEqual(len(lines), 2)
        self.assertIn(obj.version, lines[1])

    def test_pip3_install(self):
        cls = attr.make_class('Mock', ['pkg'])
        obj = cls(pkg=['a', 'b'])
        line = phase3.docker_pip3_install(obj)
        self.assertEqual(line, 'RUN pip3 install a b')

    def test_create_dockerfile(self):
        cls = attr.make_class(
            'MockRecipes',
            ['install_nodejs', 'install_rust', 'yum_install', 'pip3_install'])
        subrecipes = cls(None, None, None, None)
        cls = attr.make_class('Mock', ['from_', 'recipes', 'workdir'])
        obj = cls('baseImage', subrecipes, None)
        lines = phase3.create_dockerfile(obj)
        self.assertEqual(lines, 'FROM baseImage')
        obj.workdir = '/test'
        lines = phase3.create_dockerfile(obj)
        self.assertEqual(lines, 'FROM baseImage\nWORKDIR /test')

    @mock.patch('trask.phase3.docker_yum_install')
    @mock.patch('trask.phase3.docker_install_rust')
    @mock.patch('trask.phase3.docker_install_nodejs')
    @mock.patch('trask.phase3.docker_pip3_install')
    def test_create_dockerfile_mock(self, pip3, nodejs, rust, yum):
        pip3.return_value = 'pip3'
        nodejs.return_value = ['nodejs']
        rust.return_value = ['rust']
        yum.return_value = 'yum'
        cls = attr.make_class(
            'MockRecipes',
            ['install_nodejs', 'install_rust', 'yum_install', 'pip3_install'])
        subrecipes = cls('a', 'b', 'c', 'd')
        cls = attr.make_class('Mock', ['from_', 'recipes', 'workdir'])
        obj = cls('baseImage', subrecipes, None)
        text = phase3.create_dockerfile(obj)
        self.assertEqual(text, 'FROM baseImage\nyum\nrust\nnodejs\npip3')

    def test_handle_docker_run(self):
        cls = attr.make_class('Mock', ['init', 'volumes', 'image', 'commands'])
        obj = cls(init=False, volumes=[], image='myImage', commands=['x', 'y'])
        ctx = context_command_recorder()
        phase3.handle_docker_run(obj, ctx)
        self.assertEqual(
            ctx.commands,
            [('sudo', 'docker', 'run', 'myImage', 'sh', '-c', 'x && y')])

        obj.init = True
        vcls = attr.make_class('Volume', ['host', 'container'])
        obj.volumes = [vcls(host='/host', container='/container')]
        ctx.commands = []
        phase3.handle_docker_run(obj, ctx)
        self.assertEqual(
            ctx.commands,
            [('sudo', 'docker', 'run', '--init', '--volume',
              '/host:/container:z', 'myImage', 'sh', '-c', 'x && y')])

    @mock.patch('trask.phase3.create_dockerfile')
    def test_handle_docker_build(self, mock_dock):
        mock_dock.return_value = 'mockContents'

        cls = attr.make_class('Mock', ['tag'])
        obj = cls('myTag')

        ctx = context_command_recorder()
        phase3.handle_docker_build(obj, ctx)

        self.assertEqual(len(ctx.commands), 1)
        cmd = ctx.commands[0]

        self.assertEqual(
            cmd[0:6], ('sudo', 'docker', 'build', '--tag', 'myTag', '--file'))

        obj.tag = None
        ctx.commands = []
        phase3.handle_docker_build(obj, ctx)

        self.assertEqual(len(ctx.commands), 1)
        cmd = ctx.commands[0]

        self.assertEqual(cmd[0:4], ('sudo', 'docker', 'build', '--file'))


class TestTempDir(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def test_handle_create_temp_dir(self):
        cls = attr.make_class('Mock', ['var'])
        obj = cls('myVar')
        ctx = phase3.Context()
        phase3.handle_create_temp_dir(obj, ctx)
        path = ctx.variables['myVar']
        self.assertTrue(os.path.exists(path))
        self.assertEqual(ctx.temp_dirs[0].name, path)


class TestCopy(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.cls = attr.make_class('Mock', ['src', 'dst'])

    def test_copy_file(self):
        self.fs.create_file('/srcFile')
        self.fs.create_dir('/dstDir')

        obj = self.cls(['/srcFile'], '/dstDir')
        ctx = phase3.Context(dry_run=False)
        phase3.handle_copy(obj, ctx)

        self.assertTrue(os.path.exists('/dstDir/srcFile'))

    def test_copy_file_dry(self):
        self.fs.create_file('/srcFile')
        self.fs.create_dir('/dstDir')

        obj = self.cls(['/srcFile'], '/dstDir')
        ctx = phase3.Context(dry_run=True)
        phase3.handle_copy(obj, ctx)

        self.assertFalse(os.path.exists('/dstDir/srcFile'))

    def test_copy_dir(self):
        self.fs.create_dir('/srcDir')
        self.fs.create_dir('/dstDir')

        obj = self.cls(['/srcDir'], '/dstDir')
        ctx = phase3.Context(dry_run=False)
        phase3.handle_copy(obj, ctx)

        self.assertTrue(os.path.exists('/dstDir/srcDir/'))

    def test_copy_dir_dry(self):
        self.fs.create_dir('/srcDir')
        self.fs.create_dir('/dstDir')

        obj = self.cls(['/srcDir'], '/dstDir')
        ctx = phase3.Context(dry_run=True)
        phase3.handle_copy(obj, ctx)

        self.assertFalse(os.path.exists('/dstDir/srcDir/'))
