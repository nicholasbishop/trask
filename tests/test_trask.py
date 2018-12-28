#!/usr/bin/env python3

# pylint: disable=missing-docstring

import unittest

from pyfakefs import fake_filesystem_unittest

import trask
from trask import phase1, phase2, types


class TestGrammar(unittest.TestCase):
    def test_bool(self):
        self.assertIs(phase1.MODEL.parse('true', 'boolean'), True)
        self.assertIs(phase1.MODEL.parse('false', 'boolean'), False)

    def test_string(self):
        self.assertEqual(
            phase1.MODEL.parse("'myString'", 'string'), 'myString')

    def test_call(self):
        self.assertEqual(
            phase1.MODEL.parse("myFunc('myArg')", 'call'),
            types.Call('myFunc', ['myArg']))

    def test_list(self):
        self.assertEqual(
            phase1.MODEL.parse("['a' 'b' 'c']", 'list'), ['a', 'b', 'c'])

    def test_dictionary(self):
        text = "{a 'b'\nc 'd'}"
        self.assertEqual(
            phase1.MODEL.parse(text, 'dictionary'), {
                'a': 'b',
                'c': 'd',
            })


class TestDockerfile(unittest.TestCase):
    def test_rust(self):
        lines1 = trask.docker_install_rust({})
        lines2 = trask.docker_install_rust({'channel': 'stable'})
        lines3 = trask.docker_install_rust({'channel': 'nightly'})
        self.assertEqual(lines1, lines2)
        self.assertEqual(len(lines1) + 1, len(lines3))
        with self.assertRaises(ValueError):
            trask.docker_install_rust({'channel': 'badChannel'})


class TestPhase1(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def test_empty(self):
        self.fs.create_file('/myFile')
        result = phase1.load('/myFile')
        self.assertEqual(result, [])

    def test_include(self):
        self.fs.create_file('/a', contents="include { file '/b' }")
        self.fs.create_file('/b', contents="foo {} bar {}")
        result = phase1.load('/a')
        expected = phase1.load('/b')
        self.assertEqual(result, expected)


class TestPhase2(unittest.TestCase):
    def test_empty(self):
        schema = phase2.MODEL.parse('')
        result = phase2.Phase2.load(schema, [])
        self.assertEqual(result, [])

    def test_bool(self):
        schema = phase2.MODEL.parse('bool', 'type')
        result = phase2.Phase2.load(schema, True)
        self.assertEqual(result, True)
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, 'foo')

    def test_string(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, 'myString')
        self.assertEqual(result, 'myString')
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, True)

    def test_array(self):
        schema = phase2.MODEL.parse('string[]', 'type')
        result = phase2.Phase2.load(schema, ['a', 'b'])
        self.assertEqual(result, ['a', 'b'])
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, 'foo')
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, [True])
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, ['foo', True])

    def test_object(self):
        schema = phase2.MODEL.parse("{ foo: string; }", 'type')
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, 'bar')
        result = phase2.Phase2.load(schema, {})
        self.assertEqual(result.foo, None)
        with self.assertRaises(phase2.InvalidKey):
            phase2.Phase2.load(schema, {'bad-key': 'bar'})

    def test_required_key(self):
        schema = phase2.MODEL.parse("{ required foo: string; }", 'type')
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, 'bar')
        with self.assertRaises(phase2.MissingKey):
            phase2.Phase2.load(schema, {})

    def test_wildcard(self):
        schema = phase2.MODEL.parse("{ *: string; }", 'type')
        phase2.Phase2.load(schema, {})
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, 'bar')

    def test_choice(self):
        schema = phase2.MODEL.parse("string choices('x', 'y')", 'type')
        result = phase2.Phase2.load(schema, 'x')
        self.assertEqual(result, 'x')
        with self.assertRaises(phase2.InvalidChoice):
            phase2.Phase2.load(schema, 'foo')

    def test_var(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, types.Var('x'),
                                    {'x': types.Kind.String})
        self.assertEqual(result, types.Var('x'))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, types.Var('x'), {'x': types.Kind.Bool})
        with self.assertRaises(phase2.UnboundVariable):
            phase2.Phase2.load(schema, types.Var('x'))

    def test_call(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, types.Call('env', ('x', )))
        self.assertEqual(result, types.Call('env', ('x', )))
        with self.assertRaises(phase2.InvalidFunction):
            phase2.Phase2.load(schema, types.Call('x', ()))

    def test_set(self):
        loader = phase2.Phase2()
        result = loader.load_any(phase2.SCHEMA,
                                 [types.Step('set', {'foo': 'bar'}, None)], [])
        self.assertEqual(loader.variables, {'foo': types.Kind.String})

    # def test_path(self):
    #     schema = make_schema("foo { bar: path; }")
    #     result = schema.validate(
    #         [types.Step('foo', {'bar': 'baz'}, '/myPath')])
    #     self.assertEqual(result[0].recipe.bar, '/myPath/baz')
    #     with self.assertRaises(phase2.TypeMismatch):
    #         schema.validate([{'foo': {'bar': True}}])

    # def test_string_array(self):
    #     schema = make_schema("foo { bar: string[]; }")
    #     schema.validate([{'foo': {'bar': ['x']}}])
    #     with self.assertRaises(phase2.TypeMismatch):
    #         schema.validate([{'foo': {'bar': [True]}}])
    #     with self.assertRaises(phase2.TypeMismatch):
    #         schema.validate([{'foo': {'bar': 'x'}}])

    # def test_object_array(self):
    #     schema = make_schema("foo { bar: { baz: string; }[]; }")
    #     schema.validate([{'foo': {'bar': [{'baz': 'x'}]}}])
    #     with self.assertRaises(phase2.TypeMismatch):
    #         schema.validate([{'foo': {'bar': [True]}}])
    #     with self.assertRaises(phase2.TypeMismatch):
    #         schema.validate([{'foo': {'bar': 'baz'}}])

    # def test_validate_result(self):
    #     schema = make_schema("foo { bar: string; }")
    #     result = schema.validate(
    #         [types.Step('foo', {'bar': 'baz'}, None)])
    #     self.assertEqual(len(result), 1)
    #     obj = result[0]
    #     self.assertTrue(isinstance(obj, types.Step))
    #     obj = obj.recipe
    #     self.assertEqual(obj.__class__.__name__, 'SchemaClass')
    #     obj = obj.bar
    #     self.assertEqual(obj, 'baz')


if __name__ == '__main__':
    unittest.main()
