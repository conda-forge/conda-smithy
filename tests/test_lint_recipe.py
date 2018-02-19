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
import warnings
import github

import conda_smithy.lint_recipe as linter
_thisdir = os.path.abspath(os.path.dirname(__file__))


def is_gh_token_set():
    return 'GH_TOKEN' in os.environ


@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp('recipe_')
    yield tmp_dir
    shutil.rmtree(tmp_dir)


class Test_linter(unittest.TestCase):
    def test_bad_top_level(self):
        meta = OrderedDict([['package', {}],
                            ['build', {}],
                            ['sources', {}]])
        lints = linter.lintify(meta)
        expected_msg = ("The top level meta key sources is unexpected")
        self.assertIn(expected_msg, lints)

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

        lints = linter.lintify({'test': {'files': 'foo'}})
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
                         '``<two spaces>#<one space>[<expression>]`` form.'
                         ' See lines {}'.format([3]))

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

    def test_noarch_selectors(self):
        expected_start = "`noarch` packages can't have selectors."

        with tmp_directory() as recipe_dir:
            def assert_noarch_selector(meta_string, is_good=False):
                with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                    fh.write(meta_string)
                lints = linter.main(recipe_dir)
                if is_good:
                    message = ("Found lints when there shouldn't have "
                               "been a lint for '{}'."
                              ).format(meta_string)
                else:
                    message = ("Expected lints for '{}', but didn't "
                               "get any.").format(meta_string)
                self.assertEqual(not is_good,
                                 any(lint.startswith(expected_start)
                                     for lint in lints),
                                 message)

            assert_noarch_selector("""
                            build:
                              noarch: python
                              skip: true  # [py2k]
                            """)
            assert_noarch_selector("""
                            build:
                              noarch: generic
                              skip: true  # [win]
                            """)
            assert_noarch_selector("""
                            build:
                              noarch: python
                              skip: true  #
                            """, is_good=True)
            assert_noarch_selector("""
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [unix]
                                - echo "hello" # [win]
                            """, is_good=True)
            assert_noarch_selector("""
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [unix]
                                - echo "hello" # [win]
                              requirements:
                                build:
                                  - python
                            """, is_good=True)
            assert_noarch_selector("""
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [unix]
                                - echo "hello" # [win]
                              requirements:
                                build:
                                  - python
                              tests:
                                commands:
                                  - cp asd qwe  # [unix]
                            """, is_good=True)
            assert_noarch_selector("""
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [unix]
                                - echo "hello" # [win]
                              requirements:
                                build:
                                  - python
                                  - enum34     # [py2k]
                              tests:
                                commands:
                                  - cp asd qwe  # [unix]
                            """)

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

        meta = {'requirements': OrderedDict([['run', 'a'],
                                             ['invalid', 'a'],
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

    def test_cb3_jinja2_functions(self):
        lints = linter.main(os.path.join(_thisdir, 'recipes', 'cb3_jinja2_functions', 'recipe'))
        assert not lints

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_maintainer_exists(self):
        lints = linter.lintify({'extra': {'recipe-maintainers': ['support']}}, conda_forge=True)
        expected_message = ('Recipe maintainer "support" does not exist')
        self.assertIn(expected_message, lints)

        lints = linter.lintify({'extra': {'recipe-maintainers': ['isuruf']}}, conda_forge=True)
        expected_message = ('Recipe maintainer "isuruf" does not exist')
        self.assertNotIn(expected_message, lints)

        expected_message = 'Feedstock with the same name exists in conda-forge'
        # Check that feedstock exists if staged_recipes
        lints = linter.lintify({'package': {'name': 'python'}}, recipe_dir='python', conda_forge=True)
        self.assertIn(expected_message, lints)
        lints = linter.lintify({'package': {'name': 'python'}}, recipe_dir='python', conda_forge=False)
        self.assertNotIn(expected_message, lints)
        # No lint if in a feedstock
        lints = linter.lintify({'package': {'name': 'python'}}, recipe_dir='recipe', conda_forge=True)
        self.assertNotIn(expected_message, lints)
        lints = linter.lintify({'package': {'name': 'python'}}, recipe_dir='recipe', conda_forge=False)
        self.assertNotIn(expected_message, lints)

        # Make sure there's no feedstock named python1 before proceeding
        gh = github.Github(os.environ['GH_TOKEN'])
        cf = gh.get_user('conda-forge')
        try:
            cf.get_repo('python1-feedstock')
            feedstock_exists = True
        except github.UnknownObjectException as e:
            feedstock_exists = False

        if feedstock_exists:
            warnings.warn("There's a feedstock named python1, but tests assume that there isn't")
        else:
            lints = linter.lintify({'package': {'name': 'python1'}}, recipe_dir="python", conda_forge=True)
            self.assertNotIn(expected_message, lints)


    def test_bad_subheader(self):
        expected_message = 'The {} section contained an unexpected ' \
                           'subsection name. {} is not a valid subsection' \
                           ' name.'.format('build', 'ski')
        meta = {'build': {'skip': 'True',
                          'script': 'python setup.py install',
                          'number': 0}}
        lints = linter.lintify(meta)
        self.assertNotIn(expected_message, lints)

        meta = {'build': {'ski': 'True',
                          'script': 'python setup.py install',
                          'number': 0}}
        lints = linter.lintify(meta)
        self.assertIn(expected_message, lints)

    def test_outputs(self):
        meta = OrderedDict([['outputs', [{'name': 'asd'}]]])
        lints = linter.lintify(meta)

    def test_version(self):
        meta = {'package': {'name': 'python',
                            'version': '3.6.4'}}
        expected_message = "Package version 3.6.4 doesn't match conda spec"
        lints = linter.lintify(meta)
        self.assertNotIn(expected_message, lints)

        meta = {'package': {'name': 'python',
                            'version': '2.0.0~alpha0'}}
        expected_message = "Package version 2.0.0~alpha0 doesn't match conda spec"
        lints = linter.lintify(meta)
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
                    test:
                        imports:
                            - foo
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
                        imports:
                            - foo
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
            with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'wt', encoding='utf-8') as fh:
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
