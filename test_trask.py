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


class TestDockerfile(unittest.TestCase):
    def test_rust(self):
        lines1 = trask.docker_install_rust({})
        lines2 = trask.docker_install_rust({'channel': 'stable'})
        lines3 = trask.docker_install_rust({'channel': 'nightly'})
        self.assertEqual(lines1, lines2)
        self.assertEqual(len(lines1) + 1, len(lines3))
        with self.assertRaises(ValueError):
            trask.docker_install_rust({'channel': 'badChannel'})


if __name__ == '__main__':
    unittest.main()
