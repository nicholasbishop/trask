# pylint: disable=missing-docstring

import unittest

from pyfakefs import fake_filesystem_unittest

from trask import phase1, types


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

    def test_step_path(self):
        self.fs.create_file('/a/b/c.trask', contents="set {}")
        result = phase1.load('/a/b/c.trask')
        self.assertEqual(result[0].path, '/a/b')
