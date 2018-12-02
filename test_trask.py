#!/usr/bin/env python3

import unittest

import trask


class TestGrammar(unittest.TestCase):
    def test_bool(self):
        self.assertIs(trask.MODEL.parse('true', 'boolean'), True)
        self.assertIs(trask.MODEL.parse('false', 'boolean'), False)

    def test_string(self):
        self.assertEqual(trask.MODEL.parse("'myString'", 'string'), 'myString')

    def test_map(self):
        text = '{a: b\nc: d\nc: e}'
        self.assertEqual(trask.MODEL.parse(text, 'dictionary').pairs, {
            'a': ['b'],
            'c': ['d', 'e'],
        })


class TestSchema(unittest.TestCase):
    def test_validate_bool(self):
        schema = {'type': 'boolean'}
        trask.validate_array([True], schema)
        with self.assertRaises(TypeError):
            trask.validate_array(['myString'], schema)

    def test_validate_dict(self):
        schema = {
            'type': 'dictionary',
            'keys': {
                'a': {
                    'type': 'boolean',
                }
            }
        }
        trask.validate_array([{'a': [True]}], schema)
        with self.assertRaises(KeyError):
            trask.validate_array([{'b': [True]}], schema)
        with self.assertRaises(TypeError):
            trask.validate_array([{'a': ['blah']}], schema)


if __name__ == '__main__':
    unittest.main()
