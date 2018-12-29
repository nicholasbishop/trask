# pylint: disable=missing-docstring

import os
import unittest

import attr
from pyfakefs import fake_filesystem_unittest

from trask import functions, phase1, phase2, phase3, types


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
