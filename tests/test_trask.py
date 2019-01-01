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

    def test_parse_args(self):
        args = trask.parse_args(['/myFile.trask'])
        self.assertEqual(args.dry_run, False)
        self.assertEqual(args.path, '/myFile.trask')


class TestDryRun(unittest.TestCase):
    def test_sample1(self):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        trask.run(os.path.join(script_dir, 'sample1.trask'), dry_run=True)
