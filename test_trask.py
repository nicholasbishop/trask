#!/usr/bin/env python3

# pylint: disable=missing-docstring

import unittest

from pyfakefs import fake_filesystem_unittest

import trask
import trask_schema

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


class TestInclude(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def test_missing_file(self):
        with self.assertRaises(OSError):
            ctx = trask.Context('/foo')
            trask.handle_include(ctx, {'file': '/this/file/does/not/exist'})

    def test_include(self):
        self.fs.create_file('/myFile')
        ctx = trask.Context('/foo')
        trask.handle_include(ctx, {'file': '/myFile'})
        self.assertEqual(ctx.trask_file, '/foo')


class TestSet(unittest.TestCase):
    def test_set(self):
        ctx = trask.Context('/foo')
        trask.handle_set(ctx, {'key': 'val'})
        self.assertEqual(ctx.variables, {'key': 'val'})


def make_schema(string):
    return trask_schema.MODEL.parse(string)


class TestSchema(unittest.TestCase):
    def test_empty(self):
        trask_schema.validate({}, {})

    def test_wildcard(self):
        schema = make_schema("foo { *: string; }")
        schema.validate({'foo': {'a': 'b'}})

    def test_invalid_recipe_name(self):
        schema = make_schema("")
        with self.assertRaises(trask_schema.InvalidKey):
            schema.validate({'bad-recipe': {}})

    def test_invalid_key(self):
        schema = make_schema("foo { bar: string; }")
        with self.assertRaises(trask_schema.InvalidKey):
            schema.validate({'foo': {'bad-key': {}}})

    def test_missing_key(self):
        schema = make_schema("foo { required bar: string; }")
        with self.assertRaises(trask_schema.MissingKey):
            schema.validate({'foo': {}})

    def test_string(self):
        schema = make_schema("foo { bar: string; }")
        schema.validate({'foo': {'bar': 'baz'}})
        with self.assertRaises(trask_schema.TypeMismatch):
            schema.validate({'foo': {'bar': True}})

    def test_bool(self):
        schema = make_schema("foo { bar: bool; }")
        schema.validate({'foo': {'bar': True}})
        with self.assertRaises(trask_schema.TypeMismatch):
            schema.validate({'foo': {'bar': 'baz'}})

    def test_path(self):
        schema = make_schema("foo { bar: path; }")
        schema.validate({'foo': {'bar': 'baz'}})
        with self.assertRaises(trask_schema.TypeMismatch):
            schema.validate({'foo': {'bar': True}})

    def test_choice(self):
        schema = make_schema("foo { bar: string choices('x', 'y'); }")
        schema.validate({'foo': {'bar': 'x'}})
        with self.assertRaises(trask_schema.InvalidChoice):
            schema.validate({'foo': {'bar': 'z'}})

    def test_string_array(self):
        schema = make_schema("foo { bar: string[]; }")
        schema.validate({'foo': {'bar': ['x']}})
        with self.assertRaises(trask_schema.TypeMismatch):
            schema.validate({'foo': {'bar': [True]}})
        with self.assertRaises(trask_schema.TypeMismatch):
            schema.validate({'foo': {'bar': 'x'}})

    def test_object_array(self):
        schema = make_schema("foo { bar: { baz: string; }[]; }")
        schema.validate({'foo': {'bar': [{'baz': 'x'}]}})
        with self.assertRaises(trask_schema.TypeMismatch):
            schema.validate({'foo': {'bar': [True]}})
        with self.assertRaises(trask_schema.TypeMismatch):
            schema.validate({'foo': {'bar': 'baz'}})


if __name__ == '__main__':
    unittest.main()
