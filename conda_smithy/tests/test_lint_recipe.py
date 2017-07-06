#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
from collections import OrderedDict
from contextlib import contextmanager
import io
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
    recipe_dir = os.path.join(tmp_dir, 'recipe')
    os.mkdir(recipe_dir)
    yield recipe_dir
    shutil.rmtree(tmp_dir)


class Test_linter(unittest.TestCase):
    def test_bad_order(self):
        meta = OrderedDict([['package', {}],
                            ['build', {}],
                            ['source', {}]])
        lints = linter.lintify(meta)
        expected_msg = ("The top level meta keys are in an unexpected "
                        "order. Expecting ['package', 'source', 'build'].")
        self.assertIn(expected_msg, lints)

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

    def test_bad_about_license_family(self):
        meta = {'about': {'home': 'a URL',
                          'summary': 'A test summary',
                          'license': 'BSD 3-clause',
                          'license_family': 'BSD3'}}
        lints = linter.lintify(meta)
        expected = "about/license_family 'BSD3' not allowed"
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

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
        expected_message = ('The recipe could do with some maintainers listed '
                            'in the `extra/recipe-maintainers` section.')

        lints = linter.lintify({'extra': {'recipe-maintainers': []}})
        self.assertIn(expected_message, lints)

        # No extra section at all.
        lints = linter.lintify({})
        self.assertIn(expected_message, lints)

        lints = linter.lintify({'extra': {'recipe-maintainers': ['a']}})
        self.assertNotIn(expected_message, lints)

        expected_message = ('The "extra" section was expected to be a '
                            'dictionary, but got a list.')
        lints = linter.lintify({'extra': ['recipe-maintainers']})
        self.assertIn(expected_message, lints)

        lints = linter.lintify({'extra': {'recipe-maintainers': 'Luke'}})
        expected_message = ('Recipe maintainers should be a json list.')
        self.assertIn(expected_message, lints)

    def test_test_section(self):
        expected_message = 'The recipe must have some tests.'

        lints = linter.lintify({})
        self.assertIn(expected_message, lints)

        lints = linter.lintify({'test': {'imports': 'sys'}})
        self.assertNotIn(expected_message, lints)

    def test_test_section_with_recipe(self):
        # If we have a run_test.py file, we shouldn't need to provide
        # other tests.

        expected_message = 'The recipe must have some tests.'

        with tmp_directory() as recipe_dir:
            lints = linter.lintify({}, recipe_dir)
            self.assertIn(expected_message, lints)

            with io.open(os.path.join(recipe_dir, 'run_test.py'), 'w') as fh:
                fh.write('# foo')
            lints = linter.lintify({}, recipe_dir)
            self.assertNotIn(expected_message, lints)

    def test_selectors(self):
        expected_message = ('Selectors are suggested to take a '
                            '``<two spaces>#<one space>[<expression>]`` form.')

        with tmp_directory() as recipe_dir:
            def assert_selector(selector, is_good=True):
                with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                    fh.write("""
                            package:
                               name: foo_py2  # [py2k]
                               {}
                             """.format(selector))
                lints = linter.lintify({}, recipe_dir)
                if is_good:
                    message = ("Found lints when there shouldn't have been a "
                               "lint for '{}'.".format(selector))
                else:
                    message = ("Expecting lints for '{}', but didn't get any."
                               "".format(selector))
                self.assertEqual(not is_good,
                                 any(lint.startswith(expected_message)
                                     for lint in lints),
                                 message)

            assert_selector("name: foo_py3      # [py3k]")
            assert_selector("name: foo_py3  [py3k]", is_good=False)
            assert_selector("name: foo_py3  #[py3k]", is_good=False)
            assert_selector("name: foo_py3 # [py3k]", is_good=False)

    def test_jinja_os_environ(self):
        # Test that we can use os.environ in a recipe. We don't care about
        # the results here.
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                fh.write("""
                        {% set version = os.environ.get('WIBBLE') %}
                        package:
                           name: foo
                           version: {{ version }}
                         """)
            lints = linter.main(recipe_dir)

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

    def test_bad_requirements_order(self):
        expected_message = ("The `requirements/build` section should be "
                            "defined before the `requirements/run` section.")

        meta = {'requirements': OrderedDict([['run', 'a'],
                                             ['build', 'a']])}
        lints = linter.lintify(meta)
        self.assertIn(expected_message, lints)

        meta = {'requirements': OrderedDict([['build', 'a'],
                                             ['run', 'a']])}
        lints = linter.lintify(meta)
        self.assertNotIn(expected_message, lints)

    def test_no_sha_with_dl(self):
        expected_message = ("When defining a source/url please add a sha256, "
                            "sha1 or md5 checksum (sha256 preferably).")
        meta = {'source': {'url': None}}
        self.assertIn(expected_message, linter.lintify(meta))

        meta = {'source': {'url': None, 'sha1': None}}
        self.assertNotIn(expected_message, linter.lintify(meta))

        meta = {'source': {'url': None, 'sha256': None}}
        self.assertNotIn(expected_message, linter.lintify(meta))

        meta = {'source': {'url': None, 'md5': None}}
        self.assertNotIn(expected_message, linter.lintify(meta))

    def test_redundant_license(self):
        meta = {'about': {'home': 'a URL',
                          'summary': 'A test summary',
                          'license': 'MIT License'}}
        lints = linter.lintify(meta)
        expected_message = ('The recipe `license` should not include '
                            'the word "License".')
        self.assertIn(expected_message, lints)

    def test_recipe_name(self):
        meta = {'package': {'name': 'mp++'}}
        lints = linter.lintify(meta)
        expected_message = ('Recipe name has invalid characters. only lowercase alpha, '
                            'numeric, underscores, hyphens and dots allowed')
        self.assertIn(expected_message, lints)

    def test_end_empty_line(self):
        bad_contents = [
            # No empty lines at the end of the file
            'extra:\n  recipe-maintainers:\n    - goanpeca',
            'extra:\r  recipe-maintainers:\r    - goanpeca',
            'extra:\r\n  recipe-maintainers:\r\n    - goanpeca',
            # Two empty lines at the end of the file
            'extra:\n  recipe-maintainers:\n    - goanpeca\n\n',
            'extra:\r  recipe-maintainers:\r    - goanpeca\r\r',
            'extra:\r\n  recipe-maintainers:\r\n    - goanpeca\r\n\r\n',
            # Three empty lines at the end of the file
            'extra:\n  recipe-maintainers:\n    - goanpeca\n\n\n',
            'extra:\r  recipe-maintainers:\r    - goanpeca\r\r\r',
            'extra:\r\n  recipe-maintainers:\r\n    - goanpeca\r\n\r\n\r\n',
        ]
        # Exactly one empty line at the end of the file
        valid_content = 'extra:\n  recipe-maintainers:\n    - goanpeca\n'

        for content, lines in zip(bad_contents + [valid_content],
                                  [0, 0, 0, 2, 2, 2, 3, 3, 3, 1]):
            with tmp_directory() as recipe_dir:
                with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as f:
                    f.write(content)
                lints = linter.lintify({}, recipe_dir=recipe_dir)
                if lines > 1:
                    expected_message = ('There are {} too many lines.  '
                                        'There should be one empty line '
                                        'at the end of the '
                                        'file.'.format(lines - 1))
                else:
                    expected_message = ('There are too few lines.  '
                                        'There should be one empty line at'
                                        ' the end of the file.')
                if content == valid_content:
                    self.assertNotIn(expected_message, lints)
                else:
                    self.assertIn(expected_message, lints)


class TestCLI_recipe_lint(unittest.TestCase):
    def test_cli_fail(self):
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                fh.write(textwrap.dedent("""
                    package:
                        name: 'test_package'
                    build: []
                    requirements: []
                    """))
            child = subprocess.Popen(['conda-smithy', 'recipe-lint',
                                      recipe_dir],
                                     stdout=subprocess.PIPE)
            out, _ = child.communicate()
            self.assertEqual(child.returncode, 1, out)

    def test_cli_success(self):
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
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
            child = subprocess.Popen(['conda-smithy', 'recipe-lint',
                                      recipe_dir],
                                     stdout=subprocess.PIPE)
            out, _ = child.communicate()
            self.assertEqual(child.returncode, 0, out)

    def test_cli_environ(self):
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                fh.write(textwrap.dedent("""
                    package:
                        name: 'test_package'
                    build:
                        number: 0
                    test:
                        requires:
                            - python {{ environ['PY_VER'] + '*' }}  # [win]
                    about:
                        home: something
                        license: something else
                        summary: a test recipe
                    extra:
                        recipe-maintainers:
                            - a
                            - b
                    """))
            child = subprocess.Popen(['conda-smithy', 'recipe-lint',
                                      recipe_dir],
                                     stdout=subprocess.PIPE)
            out, _ = child.communicate()
            self.assertEqual(child.returncode, 0, out)

    def test_unicode(self):
        """
        Tests that unicode does not confuse the linter.
        """
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'wt') as fh:
                fh.write("""
                    package:
                        name: 'test_package'
                    build:
                        number: 0
                    about:
                        home: something
                        license: something else
                        summary: αβɣ
                        description: moɿɘ uniɔobɘ!
                         """)
            # Just run it and make sure it does not raise.
            linter.main(recipe_dir)


if __name__ == '__main__':
    unittest.main()
