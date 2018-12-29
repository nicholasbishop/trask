# pylint: disable=missing-docstring

import os
import unittest

import attr

from trask import phase2, phase3, types


class TestResolveValue(unittest.TestCase):
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


class TestPhase3(unittest.TestCase):
    def test_run_cmd(self):
        # pylint: disable=no-self-use
        phase3.run_cmd('true')

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
