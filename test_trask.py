#!/usr/bin/env python3

import unittest

import trask


class TestGrammar(unittest.TestCase):
    def test_bool(self):
        self.assertIs(trask.MODEL.parse('true', 'boolean'), True)
        self.assertIs(trask.MODEL.parse('false', 'boolean'), False)

    def test_string(self):
        self.assertEqual(trask.MODEL.parse("'myString'", 'string'), 'myString')

    def test_list(self):
        self.assertEqual(
            trask.MODEL.parse("['a' 'b' 'c']", 'list'), ['a', 'b', 'c'])

    def test_dictionary(self):
        text = "{a 'b'\nc 'd'\nc 'e'}"
        self.assertEqual(
            trask.MODEL.parse(text, 'dictionary').pairs, {
                'a': ['b'],
                'c': ['d', 'e'],
            })


if __name__ == '__main__':
    unittest.main()
