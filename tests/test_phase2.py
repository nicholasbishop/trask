# pylint: disable=missing-docstring

import unittest

from trask import phase2, types


class TestPhase2Primitives(unittest.TestCase):
    def test_bool(self):
        schema = phase2.MODEL.parse('bool', 'type')
        result = phase2.Phase2.load(schema, True)
        self.assertEqual(result, types.Value(True))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, 'foo')

    def test_string(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, 'myString')
        self.assertEqual(result, types.Value('myString'))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, True)

    def test_any(self):
        schema = phase2.MODEL.parse('any', 'type')
        result = phase2.Phase2.load(schema, 'myString')
        self.assertEqual(result, types.Value('myString'))
        result = phase2.Phase2.load(schema, True)
        self.assertEqual(result, types.Value(True))
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
        self.assertEqual(result, types.Value('myPath', is_path=True))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, True)

    def test_string_array(self):
        schema = phase2.MODEL.parse('string[]', 'type')
        result = phase2.Phase2.load(schema, ['a', 'b'])
        self.assertEqual(result, [types.Value('a'), types.Value('b')])
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, 'foo')
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, [True])
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, ['foo', True])

    def test_object(self):
        schema = phase2.MODEL.parse("{ foo: string; }", 'type')
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, types.Value('bar'))
        result = phase2.Phase2.load(schema, {})
        self.assertEqual(result.foo, None)
        with self.assertRaises(phase2.InvalidKey):
            phase2.Phase2.load(schema, {'bad-key': 'bar'})

    def test_required_key(self):
        schema = phase2.MODEL.parse("{ required foo: string; }", 'type')
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, types.Value('bar'))
        with self.assertRaises(phase2.MissingKey):
            phase2.Phase2.load(schema, {})

    def test_wildcard(self):
        schema = phase2.MODEL.parse("{ *: string; }", 'type')
        phase2.Phase2.load(schema, {})
        result = phase2.Phase2.load(schema, {'foo': 'bar'})
        self.assertEqual(result.foo, types.Value('bar'))

    def test_choice(self):
        schema = phase2.MODEL.parse("string choices('x', 'y')", 'type')
        result = phase2.Phase2.load(schema, 'x')
        self.assertEqual(result, types.Value('x'))
        with self.assertRaises(phase2.InvalidChoice):
            phase2.Phase2.load(schema, 'foo')

    def test_var(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, types.Var('x'),
                                    {'x': types.Kind.String})
        self.assertEqual(result, types.Value(types.Var('x')))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, types.Var('x'), {'x': types.Kind.Bool})
        with self.assertRaises(phase2.UnboundVariable):
            phase2.Phase2.load(schema, types.Var('x'))

    def test_call(self):
        schema = phase2.MODEL.parse('string', 'type')
        result = phase2.Phase2.load(schema, types.Call('env', ('x', )))
        self.assertEqual(result, types.Value(types.Call('env', ('x', ))))
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
            result, types.Value(types.Call('env', ('key', )), is_path=True))
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, True)

    def test_invalid_call_type(self):
        schema = phase2.MODEL.parse('bool', 'type')
        with self.assertRaises(phase2.TypeMismatch):
            phase2.Phase2.load(schema, types.Call('env', ('key', )))

    def test_non_object_wildcard(self):
        self.assertFalse(phase2.Type(types.Kind.Bool).wildcard_key())
