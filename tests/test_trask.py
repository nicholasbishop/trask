# pylint: disable=missing-docstring

import os
import unittest

from trask import functions


class TestFunctions(unittest.TestCase):
    def test_get_from_env(self):
        os.environ['MY_TEST_VAR'] = 'my-test-value'
        self.assertEqual(
            functions.get_from_env(('MY_TEST_VAR', )), 'my-test-value')
