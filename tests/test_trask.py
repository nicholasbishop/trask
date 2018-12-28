#!/usr/bin/env python3

# pylint: disable=missing-docstring

import os
import unittest

from pyfakefs import fake_filesystem_unittest

from trask import functions, phase1, phase2, phase3, types


class TestGrammar(unittest.TestCase):
    def test_bool(self):
        self.assertIs(phase1.MODEL.parse('true', 'boolean'), True)
        self.assertIs(phase1.MODEL.parse('false', 'boolean'), False)

    def test_invalid_bool(self):
        with self.assertRaises(ValueError):
            phase1.Semantics().boolean('invalid-bool')

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


class TestPhase1(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def test_empty(self):
        self.fs.create_file('/myFile')
        result = phase1.load('/myFile')
        self.assertEqual(result, [])

    def test_include(self):
        self.fs.create_file('/a', contents="include { file 'b' }")
        self.fs.create_file('/b', contents="foo {} bar {}")
        result = phase1.load('/a')
        expected = phase1.load('/b')
        self.assertEqual(result, expected)

    def test_include_not_variable(self):
        self.fs.create_file('/a', contents="include { file myVar }")
        with self.assertRaises(TypeError):
            phase1.load('/a')


class TestPhase2Primitives(unittest.TestCase):
    def test_bool(self):
        schema = phase2.MODEL.parse('bool', 'type')
        result = phase2.Phase2.load(schema, True)
        self.assertEqual(result, phase2.Value(True))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, 'foo')

    def test_string(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, 'myString')
        self.assertEqual(result, phase2.Value('myString'))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, True)

    def test_any(self):
        schema = phase2.MODEL.parse('any', 'type')
        result = phase2.Phase2.load(schema, 'myString')
        self.assertEqual(result, phase2.Value('myString'))
        result = phase2.Phase2.load(schema, True)
        self.assertEqual(result, phase2.Value(True))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, None)

    def test_invalid_primitive(self):
        with self.assertRaises(ValueError):
            phase2.Semantics().primitive('bad-primitive')


class TestPhase2(unittest.TestCase):
    def test_empty(self):
        schema = phase2.MODEL.parse('')
        result = phase2.Phase2.load(schema, [])
        self.assertEqual(result, [])

    def test_path(self):
        schema = phase2.MODEL.parse('path', 'type')
        result = phase2.Phase2.load(schema, 'myPath')
        self.assertEqual(result, phase2.Value('myPath', is_path=True))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, True)

    def test_string_array(self):
        schema = phase2.MODEL.parse('string[]', 'type')
        result = phase2.Phase2.load(schema, ['a', 'b'])
        self.assertEqual(result, [phase2.Value('a'), phase2.Value('b')])
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, 'foo')
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, [True])
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, ['foo', True])

    def test_object(self):
        schema = phase2.MODEL.parse("{ foo: string; }", 'type')
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, phase2.Value('bar'))
        result = phase2.Phase2.load(schema, {})
        self.assertEqual(result.foo, None)
        with self.assertRaises(phase2.InvalidKey):
            phase2.Phase2.load(schema, {'bad-key': 'bar'})

    def test_required_key(self):
        schema = phase2.MODEL.parse("{ required foo: string; }", 'type')
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, phase2.Value('bar'))
        with self.assertRaises(phase2.MissingKey):
            phase2.Phase2.load(schema, {})

    def test_wildcard(self):
        schema = phase2.MODEL.parse("{ *: string; }", 'type')
        phase2.Phase2.load(schema, {})
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, phase2.Value('bar'))

    def test_choice(self):
        schema = phase2.MODEL.parse("string choices('x', 'y')", 'type')
        result = phase2.Phase2.load(schema, 'x')
        self.assertEqual(result, phase2.Value('x'))
        with self.assertRaises(phase2.InvalidChoice):
            phase2.Phase2.load(schema, 'foo')

    def test_var(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, types.Var('x'),
                                    {'x': types.Kind.String})
        self.assertEqual(result, phase2.Value(types.Var('x')))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, types.Var('x'), {'x': types.Kind.Bool})
        with self.assertRaises(phase2.UnboundVariable):
            phase2.Phase2.load(schema, types.Var('x'))

    def test_call(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, types.Call('env', ('x', )))
        self.assertEqual(result, phase2.Value(types.Call('env', ('x', ))))
        with self.assertRaises(phase2.InvalidFunction):
            phase2.Phase2.load(schema, types.Call('x', ()))

    def test_set(self):
        loader = phase2.Phase2()
        loader.load_one(phase2.SCHEMA, [
            types.Step('set', {
                'a': 'x',
                'b': True,
                'c': types.Call('env', ('x', ))
            }, None)
        ], [])
        self.assertEqual(loader.variables, {
            'a': types.Kind.String,
            'b': types.Kind.Bool,
            'c': types.Kind.String
        })

    def test_set_bad_type(self):
        loader = phase2.Phase2()
        with self.assertRaises(phase2.SchemaError):
            loader.load_one(phase2.SCHEMA,
                            [types.Step('set', {'a': object()}, None)], [])

    def test_step(self):
        schema = phase2.MODEL.parse('foo {}')
        result = phase2.Phase2.load(schema, [types.Step('foo', {}, None)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].__class__, types.Step)
        self.assertEqual(result[0].name, 'foo')

    def test_invalid_object(self):
        schema = phase2.MODEL.parse('{}', 'type')
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, True)

    def test_set_call(self):
        loader = phase2.Phase2()
        loader.load_one(
            phase2.SCHEMA,
            [types.Step('set', {'foo': types.Call('env',
                                                  ('key', ))}, None)], [])
        self.assertEqual(loader.variables, {'foo': types.Kind.String})

    def test_create_temp_dir(self):
        loader = phase2.Phase2()
        loader.load_one(phase2.SCHEMA,
                        [types.Step('create-temp-dir', {'var': 'foo'}, None)],
                        [])
        self.assertEqual(loader.variables, {'foo': types.Kind.Path})

    def test_call_to_path(self):
        schema = phase2.MODEL.parse('path', 'type')
        result = phase2.Phase2.load(schema, types.Call('env', ('key', )))
        self.assertEqual(
            result, phase2.Value(types.Call('env', ('key', )), is_path=True))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, True)

    def test_invalid_call_type(self):
        schema = phase2.MODEL.parse('bool', 'type')
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, types.Call('env', ('key', )))

    def test_non_object_wildcard(self):
        self.assertFalse(phase2.Type(types.Kind.Bool).wildcard_key())

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


class TestValue(unittest.TestCase):
    def test_bool(self):
        self.assertEqual(phase2.Value(True).get(None), True)
        self.assertEqual(phase2.Value(False).get(None), False)

    def test_string(self):
        self.assertEqual(phase2.Value('foo').get(None), 'foo')

    def test_path(self):
        class Context:
            def repath(self, path):
                # pylint: disable=no-self-use
                return os.path.join('/root', path)

        self.assertEqual(
            phase2.Value('foo', is_path=True).get(Context()), '/root/foo')

    def test_var(self):
        this = self

        class Context:
            def resolve(self, var):
                # pylint: disable=no-self-use
                this.assertEqual(var.name, 'foo')
                return 'myResult'

        self.assertEqual(
            phase2.Value(types.Var('foo')).get(Context()), 'myResult')

    def test_var_choices(self):
        class Context:
            def resolve(self, _):
                # pylint: disable=no-self-use
                return 'z'

        self.assertEqual(
            phase2.Value(types.Var('foo', choices=('x', 'z'))).get(Context()),
            'z')
        with self.assertRaises(phase2.InvalidChoice):
            phase2.Value(types.Var('foo', choices=('x', 'y'))).get(Context())

    def test_call(self):
        this = self

        class Context:
            def call(self, call):
                # pylint: disable=no-self-use
                this.assertEqual(call.name, 'foo')
                return 'myResult'

        self.assertEqual(
            phase2.Value(types.Call('foo', ())).get(Context()), 'myResult')

    def test_invalid_value(self):
        with self.assertRaises(TypeError):
            phase2.Value(object()).get(None)


class TestFunctions(unittest.TestCase):
    def test_get_from_env(self):
        os.environ['MY_TEST_VAR'] = 'my-test-value'
        self.assertEqual(
            functions.get_from_env(('MY_TEST_VAR', )), 'my-test-value')


class TestMakeKeysSafe(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(phase2.make_keys_safe({}), {})

    def test_dash(self):
        self.assertEqual(phase2.make_keys_safe({'-': 1}), {'_': 1})

    def test_keyword(self):
        self.assertEqual(phase2.make_keys_safe({'from': 1}), {'from_': 1})


class TestPhase3(unittest.TestCase):
    def test_rust(self):
        lines1 = phase3.docker_install_rust({})
        lines2 = phase3.docker_install_rust({'channel': 'stable'})
        lines3 = phase3.docker_install_rust({'channel': 'nightly'})
        self.assertEqual(lines1, lines2)
        self.assertEqual(len(lines1) + 1, len(lines3))
        with self.assertRaises(ValueError):
            phase3.docker_install_rust({'channel': 'badChannel'})
