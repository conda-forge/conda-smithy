from __future__ import print_function
from collections import OrderedDict
from contextlib import contextmanager
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

import conda_smithy.lint_recipe as linter


@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp('recipe_')
    yield tmp_dir
    shutil.rmtree(tmp_dir)


class Test_linter(unittest.TestCase):
    def test_bad_order(self):
        meta = OrderedDict([['package', []],
                            ['build', []],
                            ['source', []]])
        lints = linter.lintify(meta)
        expected_message = "The top level meta keys are in an unexpected order. Expecting ['package', 'source', 'build']."
        self.assertIn(expected_message, lints)

    def test_missing_about_license_and_summary(self):
        meta = {'about': {'home': 'a URL'}}
        lints = linter.lintify(meta)
        expected_message = "The license item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The summary item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_missing_about_home(self):
        meta = {'about': {'license': 'BSD',
                          'summary': 'A test summary'}}
        lints = linter.lintify(meta)
        expected_message = "The home item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_missing_about_home_empty(self):
        meta = {'about': {'home': '',
                          'summary': '',
                          'license': ''}}
        lints = linter.lintify(meta)
        expected_message = "The home item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The license item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The summary item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_maintainers_section(self):
        expected_message = 'The recipe could do with some maintainers listed in the "extra/recipe-maintainers" section.'

        lints = linter.lintify({'extra': {'recipe-maintainers': []}})
        self.assertIn(expected_message, lints)
    
        # No extra section at all.
        lints = linter.lintify({})
        self.assertIn(expected_message, lints)

        lints = linter.lintify({'extra': {'recipe-maintainers': ['a']}})
        self.assertNotIn(expected_message, lints)

    def test_test_section(self):
        expected_message = 'The recipe must have some tests.'

        lints = linter.lintify({})
        self.assertIn(expected_message, lints)

        lints = linter.lintify({'test': {'imports': 'sys'}})
        self.assertNotIn(expected_message, lints)

    def test_test_section_with_recipe(self):
        # If we have a run_test.py file, we shouldn't need to provide other tests.

        expected_message = 'The recipe must have some tests.'

        with tmp_directory() as recipe_dir:
            lints = linter.lintify({}, recipe_dir)
            self.assertIn(expected_message, lints)

            with open(os.path.join(recipe_dir, 'run_test.py'), 'w') as fh:
                fh.write('# foo')
            lints = linter.lintify({}, recipe_dir)
            self.assertNotIn(expected_message, lints)


class TestCLI_recipe_lint(unittest.TestCase):
    def test_cli_fail(self):
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                fh.write(textwrap.dedent("""
                    package:
                        name: 'test_package'
                    build: []
                    requirements: []
                    """))
            child = subprocess.Popen(['conda-smithy', 'recipe-lint', recipe_dir],
                                     stdout=subprocess.PIPE)
            child.communicate()
            self.assertEqual(child.returncode, 1)
 
    def test_cli_success(self):
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                fh.write(textwrap.dedent("""
                    package:
                        name: 'test_package'
                    test: []
                    about:
                        home: something
                        license: something else
                        summary: a test recipe
                    extra:
                        recipe-maintainers:
                            - a
                            - b
                    """))
            child = subprocess.Popen(['conda-smithy', 'recipe-lint', recipe_dir],
                                     stdout=subprocess.PIPE)
            child.communicate()
            self.assertEqual(child.returncode, 0)


if __name__ == '__main__':
    unittest.main()
