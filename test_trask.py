#!/usr/bin/env python3

# pylint: disable=missing-docstring

import unittest

import trask


class TestGrammar(unittest.TestCase):
    def test_bool(self):
        self.assertIs(trask.MODEL.parse('true', 'boolean'), True)
        self.assertIs(trask.MODEL.parse('false', 'boolean'), False)

    def test_string(self):
        self.assertEqual(trask.MODEL.parse("'myString'", 'string'), 'myString')

    def test_call(self):
        self.assertEqual(trask.MODEL.parse("myFunc('myArg')", 'call'),
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


if __name__ == '__main__':
    unittest.main()
