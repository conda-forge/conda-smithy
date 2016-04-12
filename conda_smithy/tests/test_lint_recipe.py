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
        meta = OrderedDict([['package', {}],
                            ['build', {}],
                            ['source', {}]])
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

    def test_bad_about_license(self):
        meta = {'about': {'home': 'a URL',
                          'summary': 'A test summary',
                          'license': 'unknown'}}
        lints = linter.lintify(meta)
        expected_message = "The recipe license cannot be unknown."
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

    def test_selectors(self):
        expected_message = 'Selectors are suggested to take a "  # [<selector>]" form.'

        with tmp_directory() as recipe_dir:
            def assert_selector(selector, is_good=True):
                with open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                    fh.write("""
                            package:
                               name: foo_py2  # [py2k]
                               {}
                             """.format(selector))
                lints = linter.lintify({}, recipe_dir)
                if is_good:
                    message = "Found lints when there shouldn't have been a lint for '{}'.".format(selector)
                else:
                    message = "Expecting lints for '{}', but didn't get any.".format(selector)
                self.assertEqual(not is_good,
                                 any(lint.startswith(expected_message) for lint in lints),
                                 message)

            assert_selector("name: foo_py3      # [py3k]")
            assert_selector("name: foo_py3  [py3k]", is_good=False)
            assert_selector("name: foo_py3  #[py3k]", is_good=False)
            assert_selector("name: foo_py3 # [py3k]", is_good=False)

    def test_missing_build_number(self):

        expected_message = "The recipe must have a `build/number` section."

        meta = {'build': {'skip': 'True',
                          'script': 'python setup.py install',
                          'number': 0}}
        lints = linter.lintify(meta)
        self.assertNotIn(expected_message, lints)

        meta = {'build': {'skip': 'True',
                          'script': 'python setup.py install'}}
        lints = linter.lintify(meta)
        self.assertIn(expected_message, lints)


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
            out, _ = child.communicate()
            self.assertEqual(child.returncode, 1, out)

    def test_cli_success(self):
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                fh.write(textwrap.dedent("""
                    package:
                        name: 'test_package'
                    build:
                        number: 0
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
            out, _ = child.communicate()
            self.assertEqual(child.returncode, 0, out)


if __name__ == '__main__':
    unittest.main()
