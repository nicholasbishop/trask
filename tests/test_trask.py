# pylint: disable=missing-docstring

import os
import unittest

from pyfakefs import fake_filesystem_unittest

import trask
from trask import functions


class TestFunctions(unittest.TestCase):
    def test_get_from_env(self):
        os.environ['MY_TEST_VAR'] = 'my-test-value'
        self.assertEqual(
            functions.get_from_env(('MY_TEST_VAR', )), 'my-test-value')


class TestInit(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def test_run(self):
        self.fs.create_file('/myFile.trask')
        trask.run('/myFile.trask', dry_run=True)
