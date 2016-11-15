#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import io
import os
import subprocess
import textwrap
from collections import OrderedDict

import conda_smithy.lint_recipe as linter


class Test_linter(object):
    def test_bad_order(self):
        meta = OrderedDict([['package', {}],
                            ['build', {}],
                            ['source', {}]])
        lints = linter.lintify(meta)
        expected_msg = ("The top level meta keys are in an unexpected "
                        "order. Expecting ['package', 'source', 'build'].")
        assert expected_msg in lints

    def test_missing_about_license_and_summary(self):
        meta = {'about': {'home': 'a URL'}}
        lints = linter.lintify(meta)
        expected_message = "The license item is expected in the about section."
        assert expected_message in lints

        expected_message = "The summary item is expected in the about section."
        assert expected_message in lints

    def test_bad_about_license(self):
        meta = {'about': {'home': 'a URL',
                          'summary': 'A test summary',
                          'license': 'unknown'}}
        lints = linter.lintify(meta)
        expected_message = "The recipe license cannot be unknown."
        assert expected_message in lints

    def test_bad_about_license_family(self):
        meta = {'about': {'home': 'a URL',
                          'summary': 'A test summary',
                          'license': 'BSD 3-clause',
                          'license_family': 'BSD3'}}
        lints = linter.lintify(meta)
        expected = "about/license_family 'BSD3' not allowed"
        assert any(lint.startswith(expected) for lint in lints)

    def test_missing_about_home(self):
        meta = {'about': {'license': 'BSD',
                          'summary': 'A test summary'}}
        lints = linter.lintify(meta)
        expected_message = "The home item is expected in the about section."
        assert expected_message in lints

    def test_missing_about_home_empty(self):
        meta = {'about': {'home': '',
                          'summary': '',
                          'license': ''}}
        lints = linter.lintify(meta)
        expected_message = "The home item is expected in the about section."
        assert expected_message in lints

        expected_message = "The license item is expected in the about section."
        assert expected_message in lints

        expected_message = "The summary item is expected in the about section."
        assert expected_message in lints

    def test_maintainers_section(self):
        expected_message = ('The recipe could do with some maintainers listed '
                            'in the `extra/recipe-maintainers` section.')

        lints = linter.lintify({'extra': {'recipe-maintainers': []}})
        assert expected_message in lints

        # No extra section at all.
        lints = linter.lintify({})
        assert expected_message in lints

        lints = linter.lintify({'extra': {'recipe-maintainers': ['a']}})
        assert expected_message not in lints

        expected_message = ('The "extra" section was expected to be a '
                            'dictionary, but got a list.')
        lints = linter.lintify({'extra': ['recipe-maintainers']})
        assert expected_message in lints

    def test_test_section(self):
        expected_message = 'The recipe must have some tests.'

        lints = linter.lintify({})
        assert expected_message in lints

        lints = linter.lintify({'test': {'imports': 'sys'}})
        assert expected_message not in lints

    def test_test_section_with_recipe(self, tmpdir):
        # If we have a run_test.py file, we shouldn't need to provide
        # other tests.

        expected_message = 'The recipe must have some tests.'

        lints = linter.lintify({}, str(tmpdir))
        assert expected_message in lints

        with io.open(os.path.join(str(tmpdir), 'run_test.py'), 'w') as fh:
            fh.write('# foo')
        lints = linter.lintify({}, str(tmpdir))
        assert expected_message not in lints

    def test_selectors(self, tmpdir):
        expected_message = ('Selectors are suggested to take a '
                            '``<two spaces>#<one space>[<expression>]`` form.')

        recipe_dir = str(tmpdir)

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
            assert (not is_good) == \
                             any(lint.startswith(expected_message)
                                 for lint in lints), \
                             message

        assert_selector("name: foo_py3      # [py3k]")
        assert_selector("name: foo_py3  [py3k]", is_good=False)
        assert_selector("name: foo_py3  #[py3k]", is_good=False)
        assert_selector("name: foo_py3 # [py3k]", is_good=False)

    def test_jinja_os_environ(self, tmpdir):
        # Test that we can use os.environ in a recipe. We don't care about
        # the results here.
        recipe_dir = str(tmpdir)
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
        assert expected_message not in lints

        meta = {'build': {'skip': 'True',
                          'script': 'python setup.py install'}}
        lints = linter.lintify(meta)
        assert expected_message in lints

    def test_bad_requirements_order(self):
        expected_message = ("The `requirements/build` section should be "
                            "defined before the `requirements/run` section.")

        meta = {'requirements': OrderedDict([['run', 'a'],
                                             ['build', 'a']])}
        lints = linter.lintify(meta)
        assert expected_message in lints

        meta = {'requirements': OrderedDict([['build', 'a'],
                                             ['run', 'a']])}
        lints = linter.lintify(meta)
        assert expected_message not in lints

    def test_no_sha_with_dl(self):
        expected_message = ("When defining a source/url please add a sha256, "
                            "sha1 or md5 checksum (sha256 preferably).")
        meta = {'source': {'url': None}}
        assert expected_message in linter.lintify(meta)

        meta = {'source': {'url': None, 'sha1': None}}
        assert expected_message not in linter.lintify(meta)

        meta = {'source': {'url': None, 'sha256': None}}
        assert expected_message not in linter.lintify(meta)

        meta = {'source': {'url': None, 'md5': None}}
        assert expected_message not in linter.lintify(meta)

    def test_redundant_license(self):
        meta = {'about': {'home': 'a URL',
                          'summary': 'A test summary',
                          'license': 'MIT License'}}
        lints = linter.lintify(meta)
        expected_message = ('The recipe `license` should not include '
                            'the word "License".')
        assert expected_message in lints

    def test_end_empty_line(self, tmpdir):
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

        for content in bad_contents + [valid_content]:
            recipe_dir = str(tmpdir)
            with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as f:
                f.write(content)
            lints = linter.lintify({}, recipe_dir=recipe_dir)
            expected_message = ('There should be one empty line at the '
                                'end of the file.')
            if content == valid_content:
                assert expected_message not in lints
            else:
                assert expected_message in lints


class TestCLI_recipe_lint(object):
    def test_cli_fail(self, tmpdir):
        recipe_dir = str(tmpdir)
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
        assert child.returncode == 1, out

    def test_cli_success(self, tmpdir):
        recipe_dir = str(tmpdir)
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
        assert child.returncode == 0, out

    def test_cli_environ(self, tmpdir):
        recipe_dir = str(tmpdir)
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
        assert child.returncode == 0, out

    def test_unicode(self, tmpdir):
        """
        Tests that unicode does not confuse the linter.
        """
        recipe_dir = str(tmpdir)
        with io.open(os.path.join(recipe_dir, 'meta.yaml'), 'wt', encoding='UTF-8') as fh:
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

