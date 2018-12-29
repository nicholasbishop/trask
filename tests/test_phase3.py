# pylint: disable=missing-docstring

import os
import unittest

import attr

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

    def test_handle_ssh(self):
        cls = attr.make_class('Mock', ['identity', 'user', 'host', 'commands'])
        obj = cls(
            identity='/myId', user='me', host='myHost', commands=['a', 'b'])

        ctx = phase3.Context()
        actual_args = None

        def mock_run_cmd(*args):
            nonlocal actual_args
            actual_args = args

        ctx.run_cmd = mock_run_cmd

        phase3.handle_ssh(obj, ctx)
        self.assertEqual(actual_args,
                         ('ssh', '-i', '/myId', 'me@myHost', 'a && b'))

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

        actual_args = []

        def mock_run_cmd(*args):
            actual_args.append(args)

        ctx = phase3.Context()
        ctx.run_cmd = mock_run_cmd

        phase3.handle_upload(obj, ctx)
        self.assertEqual(
            actual_args,
            [('scp', '-i', '/myId', '-r', '/src', 'me@myHost:/dst')])

        obj.replace = True
        actual_args = []
        phase3.handle_upload(obj, ctx)
        self.assertEqual(
            actual_args,
            [('ssh', '-i', '/myId', 'me@myHost', 'rm', '-fr', '/dst'),
             ('scp', '-i', '/myId', '-r', '/src', 'me@myHost:/dst')])

    def test_run(self):
        cls = attr.make_class('MockSet', ['a'])
        recipe = cls(types.Value('b'))
        steps = [types.Step('set', recipe, None)]
        ctx = phase3.Context()
        phase3.run(steps, ctx)
        self.assertEqual(ctx.variables, {'a': 'b'})
