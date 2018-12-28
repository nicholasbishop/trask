#!/usr/bin/env python3

# pylint: disable=missing-docstring

import unittest

from pyfakefs import fake_filesystem_unittest

import trask


class TestGrammar(unittest.TestCase):
    def test_bool(self):
        self.assertIs(trask.MODEL.parse('true', 'boolean'), True)
        self.assertIs(trask.MODEL.parse('false', 'boolean'), False)

    def test_string(self):
        self.assertEqual(trask.MODEL.parse("'myString'", 'string'), 'myString')

    def test_call(self):
        self.assertEqual(
            trask.MODEL.parse("myFunc('myArg')", 'call'),
            trask.Call('myFunc', ['myArg']))

    def test_list(self):
        self.assertEqual(
            trask.MODEL.parse("['a' 'b' 'c']", 'list'), ['a', 'b', 'c'])

    def test_dictionary(self):
        text = "{a 'b'\nc 'd'}"
        self.assertEqual(
            trask.MODEL.parse(text, 'dictionary'), {
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
        result = trask.load_phase1('/myFile')
        self.assertEqual(result, [])

    def test_include(self):
        self.fs.create_file('/a', contents="include { file '/b' }")
        self.fs.create_file('/b', contents="foo {} bar {}")
        result = trask.load_phase1('/a')
        expected = trask.load_phase1('/b')
        self.assertEqual(result, expected)


class TestPhase2(unittest.TestCase):
    def test_empty(self):
        schema = trask.schema.MODEL.parse('')
        result = trask.schema.Phase2.load(schema, [])
        self.assertEqual(result, [])

    def test_bool(self):
        schema = trask.schema.MODEL.parse('bool', 'type')
        result = trask.schema.Phase2.load(schema, True)
        self.assertEqual(result, True)
        with self.assertRaises(trask.schema.TypeMismatch):
            trask.schema.Phase2.load(schema, 'foo')

    def test_string(self):
        schema = trask.schema.MODEL.parse('string', 'type')
        result = trask.schema.Phase2.load(schema, 'myString')
        self.assertEqual(result, 'myString')
        with self.assertRaises(trask.schema.TypeMismatch):
            trask.schema.Phase2.load(schema, True)

    def test_array(self):
        schema = trask.schema.MODEL.parse('string[]', 'type')
        result = trask.schema.Phase2.load(schema, ['a', 'b'])
        self.assertEqual(result, ['a', 'b'])
        with self.assertRaises(trask.schema.TypeMismatch):
            trask.schema.Phase2.load(schema, 'foo')
        with self.assertRaises(trask.schema.TypeMismatch):
            trask.schema.Phase2.load(schema, [True])
        with self.assertRaises(trask.schema.TypeMismatch):
            trask.schema.Phase2.load(schema, ['foo', True])

    def test_object(self):
        schema = trask.schema.MODEL.parse("{ foo: string; }", 'type')
        result = trask.schema.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, 'bar')
        result = trask.schema.Phase2.load(schema, {})
        self.assertEqual(result.foo, None)
        with self.assertRaises(trask.schema.InvalidKey):
            trask.schema.Phase2.load(schema, {'bad-key': 'bar'})

    def test_required_key(self):
        schema = trask.schema.MODEL.parse("{ required foo: string; }", 'type')
        result = trask.schema.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, 'bar')
        with self.assertRaises(trask.schema.MissingKey):
            trask.schema.Phase2.load(schema, {})

    def test_wildcard(self):
        schema = trask.schema.MODEL.parse("{ *: string; }", 'type')
        trask.schema.Phase2.load(schema, {})
        result = trask.schema.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, 'bar')

    # def test_path(self):
    #     schema = make_schema("foo { bar: path; }")
    #     result = schema.validate(
    #         [trask.types.Step('foo', {'bar': 'baz'}, '/myPath')])
    #     self.assertEqual(result[0].recipe.bar, '/myPath/baz')
    #     with self.assertRaises(trask.schema.TypeMismatch):
    #         schema.validate([{'foo': {'bar': True}}])

    # def test_choice(self):
    #     schema = make_schema("foo { bar: string choices('x', 'y'); }")
    #     schema.validate([{'foo': {'bar': 'x'}}])
    #     with self.assertRaises(trask.schema.InvalidChoice):
    #         schema.validate([{'foo': {'bar': 'z'}}])

    # def test_string_array(self):
    #     schema = make_schema("foo { bar: string[]; }")
    #     schema.validate([{'foo': {'bar': ['x']}}])
    #     with self.assertRaises(trask.schema.TypeMismatch):
    #         schema.validate([{'foo': {'bar': [True]}}])
    #     with self.assertRaises(trask.schema.TypeMismatch):
    #         schema.validate([{'foo': {'bar': 'x'}}])

    # def test_object_array(self):
    #     schema = make_schema("foo { bar: { baz: string; }[]; }")
    #     schema.validate([{'foo': {'bar': [{'baz': 'x'}]}}])
    #     with self.assertRaises(trask.schema.TypeMismatch):
    #         schema.validate([{'foo': {'bar': [True]}}])
    #     with self.assertRaises(trask.schema.TypeMismatch):
    #         schema.validate([{'foo': {'bar': 'baz'}}])

    # def test_validate_result(self):
    #     schema = make_schema("foo { bar: string; }")
    #     result = schema.validate(
    #         [trask.types.Step('foo', {'bar': 'baz'}, None)])
    #     self.assertEqual(len(result), 1)
    #     obj = result[0]
    #     self.assertTrue(isinstance(obj, trask.types.Step))
    #     obj = obj.recipe
    #     self.assertEqual(obj.__class__.__name__, 'SchemaClass')
    #     obj = obj.bar
    #     self.assertEqual(obj, 'baz')


if __name__ == '__main__':
    unittest.main()
