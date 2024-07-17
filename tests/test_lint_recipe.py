#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
import pytest

import conda_smithy.lint_recipe as linter


_thisdir = os.path.abspath(os.path.dirname(__file__))


def is_gh_token_set():
    return "GH_TOKEN" in os.environ


@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp("recipe_")
    yield tmp_dir
    shutil.rmtree(tmp_dir)


@pytest.mark.parametrize(
    "comp_lang",
    ["c", "cxx", "fortran", "rust", "m2w64_c", "m2w64_cxx", "m2w64_fortran"],
)
def test_stdlib_lint(comp_lang):
    expected_message = "This recipe is using a compiler"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                f"""
                package:
                   name: foo
                requirements:
                  build:
                    # since we're in an f-string: double up braces (2->4)
                    - {{{{ compiler("{comp_lang}") }}}}
                """
            )

        lints, _ = linter.main(recipe_dir, return_hints=True)
        assert any(lint.startswith(expected_message) for lint in lints)


@pytest.mark.parametrize(
    "comp_lang",
    ["c", "cxx", "fortran", "rust", "m2w64_c", "m2w64_cxx", "m2w64_fortran"],
)
def test_rattler_stdlib_hint(comp_lang):
    expected_message = "This recipe is using a compiler"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                requirements:
                  build:
                    # since we're in an f-string: double up braces (2->4)
                    - ${{{{ compiler('{comp_lang}') }}}}
                """.format(
                    comp_lang=comp_lang
                )
            )

        with io.open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
            fh.write("conda_build_tool: rattler-build")

        _, hints = linter.main(
            recipe_dir, feedstock_dir=recipe_dir, return_hints=True
        )
        assert any(h.startswith(expected_message) for h in hints)


def test_sysroot_lint():
    expected_message = "You're setting a requirement on sysroot"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                requirements:
                  build:
                    - sysroot_{{ target_platform }} 2.17
                """
            )

        lints, _ = linter.main(recipe_dir, return_hints=True)
        assert any(lint.startswith(expected_message) for lint in lints)


def test_rattler_sysroot_hint():
    expected_message = "You're setting a requirement on sysroot"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                requirements:
                  build:
                    - sysroot_linux-64 2.17
                """
            )

        with io.open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
            fh.write("conda_build_tool: rattler-build")

        _, hints = linter.main(
            recipe_dir, return_hints=True, feedstock_dir=recipe_dir
        )
        assert any(h.startswith(expected_message) for h in hints)


@pytest.mark.parametrize("where", ["run", "run_constrained"])
def test_osx_lint(where):
    expected_message = "You're setting a constraint on the `__osx` virtual"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                f"""
                package:
                   name: foo
                requirements:
                  {where}:
                    # since we're in an f-string: double up braces (2->4)
                    - __osx >={{{{ MACOSX_DEPLOYMENT_TARGET|default("10.9") }}}}  # [osx and x86_64]
                """
            )

        lints, _ = linter.main(recipe_dir, return_hints=True)
        assert any(lint.startswith(expected_message) for lint in lints)


def test_rattler_osx_hint():
    expected_message = "You're setting a constraint on the `__osx` virtual"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                requirements:
                  run:
                    # since we're in an f-string: double up braces (2->4)
                    - if: osx
                      then:
                        - __osx >=${{ MACOSX_DEPLOYMENT_TARGET|default("10.9") }}
                """
            )

        with io.open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
            fh.write("conda_build_tool: rattler-build")

        _, hints = linter.main(
            recipe_dir, return_hints=True, feedstock_dir=recipe_dir
        )
        assert any(h.startswith(expected_message) for h in hints)


def test_stdlib_lints_multi_output():
    expected_message = "You're setting a requirement on sysroot"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                requirements:
                  build:
                    - {{ compiler("c") }}
                    # global build reqs intentionally correct; want to check outputs
                    - {{ stdlib("c") }}
                outputs:
                  - name: bar
                    requirements:
                      build:
                        # missing stdlib
                        - {{ compiler("c") }}
                  - name: baz
                    requirements:
                      build:
                        - {{ compiler("c") }}
                        - {{ stdlib("c") }}
                        - sysroot_linux-64
                  - name: quux
                    requirements:
                      run:
                        - __osx >=10.13
                  # test that cb2-style requirements don't break linter
                  - name: boing
                    requirements:
                      - bar
                """
            )

        lints, _ = linter.main(recipe_dir, return_hints=True)
        exp_stdlib = "This recipe is using a compiler"
        exp_sysroot = "You're setting a requirement on sysroot"
        exp_osx = "You're setting a constraint on the `__osx`"
        assert any(lint.startswith(exp_stdlib) for lint in lints)
        assert any(lint.startswith(exp_sysroot) for lint in lints)
        assert any(lint.startswith(exp_osx) for lint in lints)


@pytest.mark.parametrize("where", ["run", "run_constrained"])
def test_osx_noarch_hint(where):
    # don't warn on packages that are using __osx as a noarch-marker, see
    # https://conda-forge.org/docs/maintainer/knowledge_base/#noarch-packages-with-os-specific-dependencies
    avoid_message = "You're setting a constraint on the `__osx` virtual"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                f"""
                package:
                   name: foo
                requirements:
                  {where}:
                    - __osx  # [osx]
                """
            )

        _, hints = linter.main(recipe_dir, return_hints=True)
        assert not any(h.startswith(avoid_message) for h in hints)


def test_rattler_osx_noarch_hint():
    # don't warn on packages that are using __osx as a noarch-marker, see
    # https://conda-forge.org/docs/maintainer/knowledge_base/#noarch-packages-with-os-specific-dependencies
    avoid_message = "You're setting a constraint on the `__osx` virtual"

    with tmp_directory() as recipe_dir:
        with io.open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                requirements:
                  run:
                    - if: osx
                      then: __osx
                """
            )

        with io.open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
            fh.write("conda_build_tool: rattler-build")

        _, hints = linter.main(
            recipe_dir, return_hints=True, feedstock_dir=recipe_dir
        )
        assert not any(h.startswith(avoid_message) for h in hints)


@pytest.mark.parametrize(
    "std_selector",
    ["unix", "linux or (osx and x86_64)"],
    ids=["plain", "or-conjunction"],
)
@pytest.mark.parametrize("with_linux", [True, False])
@pytest.mark.parametrize(
    "reverse_arch",
    # we reverse x64/arm64 separately per deployment target, stdlib & sdk
    [(False, False, False), (True, True, True), (False, True, False)],
    ids=["False", "True", "mixed"],
)
@pytest.mark.parametrize(
    "macdt,v_std,sdk,exp_lint",
    [
        # matching -> no warning
        (["10.9", "11.0"], ["10.9", "11.0"], None, None),
        # mismatched length -> no warning (leave it to rerender)
        (["10.9", "11.0"], ["10.9"], None, None),
        # mismatch between stdlib and deployment target -> warn
        (["10.9", "11.0"], ["10.13", "11.0"], None, "Conflicting spec"),
        (["10.13", "11.0"], ["10.13", "12.3"], None, "Conflicting spec"),
        # only deployment target -> warn
        (["10.13", "11.0"], None, None, "In your conda_build_config.yaml"),
        # only stdlib -> no warning
        (None, ["10.13", "11.0"], None, None),
        (None, ["10.15"], None, None),
        # only stdlib, but outdated -> warn
        (None, ["10.9", "11.0"], None, "You are"),
        (None, ["10.9"], None, "You are"),
        # sdk below stdlib / deployment target -> warn
        (["10.13", "11.0"], ["10.13", "11.0"], ["10.12"], "You are"),
        (["10.13", "11.0"], ["10.13", "11.0"], ["10.12", "12.0"], "You are"),
        # sdk above stdlib / deployment target -> no warning
        (["10.13", "11.0"], ["10.13", "11.0"], ["12.0", "12.0"], None),
        # only one sdk version, not universally below deployment target
        # -> no warning (because we don't know enough to diagnose)
        (["10.13", "11.0"], ["10.13", "11.0"], ["10.15"], None),
        # mismatched version + wrong sdk; requires merge logic to work before
        # checking sdk version; to avoid unnecessary complexity in the exp_hint
        # handling below, repeat same test twice with different expected hints
        (["10.9", "11.0"], ["10.13", "11.0"], ["10.12"], "Conflicting spec"),
        (["10.9", "11.0"], ["10.13", "11.0"], ["10.12"], "You are"),
        # only sdk -> no warning
        (None, None, ["10.13"], None),
        (None, None, ["10.14", "12.0"], None),
        # only sdk, but below global baseline -> warning
        (None, None, ["10.12"], "You are"),
        (None, None, ["10.12", "11.0"], "You are"),
    ],
)
def test_cbc_osx_lints(
    std_selector, with_linux, reverse_arch, macdt, v_std, sdk, exp_lint
):
    with tmp_directory() as rdir:
        with open(os.path.join(rdir, "meta.yaml"), "w") as fh:
            fh.write("package:\n   name: foo")
        with open(os.path.join(rdir, "conda_build_config.yaml"), "a") as fh:
            if macdt is not None:
                fh.write(
                    f"""\
MACOSX_DEPLOYMENT_TARGET:   # [osx]
  - {macdt[0]}              # [osx and {"arm64" if reverse_arch[0] else "x86_64"}]
  - {macdt[1]}              # [osx and {"x86_64" if reverse_arch[0] else "arm64"}]
"""
                )
            if v_std is not None or with_linux:
                arch1 = "arm64" if reverse_arch[1] else "x86_64"
                arch2 = "x86_64" if reverse_arch[1] else "arm64"
                fh.write(f"c_stdlib_version:          # [{std_selector}]")
                if v_std is not None:
                    fh.write(f"\n  - {v_std[0]}       # [osx and {arch1}]")
                if v_std is not None and len(v_std) > 1:
                    fh.write(f"\n  - {v_std[1]}       # [osx and {arch2}]")
                if with_linux:
                    # to check that other stdlib specifications don't mess us up
                    fh.write("\n  - 2.17              # [linux]")
            if sdk is not None:
                # often SDK is set uniformly for osx; test this as well
                fh.write(
                    f"""
MACOSX_SDK_VERSION:         # [osx]
  - {sdk[0]}                # [osx and {"arm64" if reverse_arch[2] else "x86_64"}]
  - {sdk[1]}                # [osx and {"x86_64" if reverse_arch[2] else "arm64"}]
"""
                    if len(sdk) == 2
                    else f"""
MACOSX_SDK_VERSION:         # [osx]
  - {sdk[0]}                # [osx]
"""
                )
        # run the linter
        lints, _ = linter.main(rdir, return_hints=True)
        # show CBC/hints for debugging
        with open(os.path.join(rdir, "conda_build_config.yaml"), "r") as fh:
            print("".join(fh.readlines()))
            print(lints)
        # validate against expectations
        if exp_lint is None:
            for slug in [
                "Conflicting spec",
                "You are",
                "In your conda_build_config.yaml",
            ]:
                assert not any(lint.startswith(slug) for lint in lints)
        else:
            assert any(lint.startswith(exp_lint) for lint in lints)


@pytest.mark.parametrize(
    "std_selector",
    ["unix", "linux or (osx and x86_64)"],
    ids=["plain", "or-conjunction"],
)
@pytest.mark.parametrize("with_linux", [True, False])
@pytest.mark.parametrize(
    "reverse_arch",
    # we reverse x64/arm64 separately per deployment target, stdlib & sdk
    [(False, False, False), (True, True, True), (False, True, False)],
    ids=["False", "True", "mixed"],
)
@pytest.mark.parametrize(
    "macdt,v_std,sdk,exp_hint",
    [
        # matching -> no warning
        (["10.9", "11.0"], ["10.9", "11.0"], None, None),
        # mismatched length -> no warning (leave it to rerender)
        (["10.9", "11.0"], ["10.9"], None, None),
        # mismatch between stdlib and deployment target -> warn
        (["10.9", "11.0"], ["10.13", "11.0"], None, "Conflicting spec"),
        (["10.13", "11.0"], ["10.13", "12.3"], None, "Conflicting spec"),
        # only deployment target -> warn
        (["10.13", "11.0"], None, None, "In your conda_build_config.yaml"),
        # only stdlib -> no warning
        (None, ["10.13", "11.0"], None, None),
        (None, ["10.15"], None, None),
        # only stdlib, but outdated -> warn
        (None, ["10.9", "11.0"], None, "You are"),
        (None, ["10.9"], None, "You are"),
        # sdk below stdlib / deployment target -> warn
        (["10.13", "11.0"], ["10.13", "11.0"], ["10.12"], "You are"),
        (["10.13", "11.0"], ["10.13", "11.0"], ["10.12", "12.0"], "You are"),
        # sdk above stdlib / deployment target -> no warning
        (["10.13", "11.0"], ["10.13", "11.0"], ["12.0", "12.0"], None),
        # only one sdk version, not universally below deployment target
        # -> no warning (because we don't know enough to diagnose)
        (["10.13", "11.0"], ["10.13", "11.0"], ["10.15"], None),
        # mismatched version + wrong sdk; requires merge logic to work before
        # checking sdk version; to avoid unnecessary complexity in the exp_hint
        # handling below, repeat same test twice with different expected hints
        (["10.9", "11.0"], ["10.13", "11.0"], ["10.12"], "Conflicting spec"),
        (["10.9", "11.0"], ["10.13", "11.0"], ["10.12"], "You are"),
        # only sdk -> no warning
        (None, None, ["10.13"], None),
        (None, None, ["10.14", "12.0"], None),
        # only sdk, but below global baseline -> warning
        (None, None, ["10.12"], "You are"),
        (None, None, ["10.12", "11.0"], "You are"),
    ],
)
def test_rattler_cbc_osx_hints(
    std_selector, with_linux, reverse_arch, macdt, v_std, sdk, exp_hint
):
    with tmp_directory() as recipe_dir:
        with open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
            fh.write("package:\n   name: foo")
        with io.open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
            fh.write("conda_build_tool: rattler-build")

        with open(os.path.join(recipe_dir, "variants.yaml"), "a") as fh:
            if macdt is not None:
                fh.write(
                    f"""\
MACOSX_DEPLOYMENT_TARGET:
  - if: osx
    then:
      - {macdt[0]}
      - {macdt[1]}

"""
                )
            if v_std is not None or with_linux:
                arch1 = "arm64" if reverse_arch[1] else "x86_64"
                arch2 = "x86_64" if reverse_arch[1] else "arm64"

                fh.write("c_stdlib_version:")

                if v_std is not None:
                    fh.write(
                        f"""
  - if: {std_selector} and {arch1}
    then: {v_std[0]}
"""
                    )
                if v_std is not None and len(v_std) > 1:
                    fh.write(
                        f"""
  - if: {std_selector} and {arch2}
    then: {v_std[1]}
"""
                    )
                if with_linux:
                    fh.write(
                        """
  - if: linux
    then: 2.17
"""
                    )
            if sdk is not None:
                # often SDK is set uniformly for osx; test this as well
                fh.write(
                    f"""
MACOSX_SDK_VERSION:
  - if: osx and {"arm64" if reverse_arch[2] else "x86_64"}
    then: {sdk[0]}
  - if: osx and {"x86_64" if reverse_arch[2] else "arm64"}
    then: {sdk[1]}
"""
                    if len(sdk) == 2
                    else f"""
MACOSX_SDK_VERSION:
  - if: osx
    then: {sdk[0]}
"""
                )
        # run the linter
        _, hints = linter.main(
            recipe_dir, return_hints=True, feedstock_dir=recipe_dir
        )
        # show CBC/hints for debugging
        with open(os.path.join(recipe_dir, "variants.yaml"), "r") as fh:
            print("".join(fh.readlines()))
            print(hints)
        # validate against expectations
        if exp_hint is None:
            assert not hints
        else:
            assert any(h.startswith(exp_hint) for h in hints)


class Test_linter(unittest.TestCase):
    def test_pin_compatible_in_run_exports(self):
        meta = {
            "package": {
                "name": "apackage",
            },
            "build": {
                "run_exports": ["compatible_pin apackage"],
            },
        }
        lints, hints = linter.lintify_recipe(meta)
        expected = "pin_subpackage should be used instead"
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

    def test_pin_compatible_in_run_exports_output(self):
        meta = {
            "package": {
                "name": "apackage",
            },
            "outputs": [
                {
                    "name": "anoutput",
                    "build": {
                        "run_exports": ["subpackage_pin notanoutput"],
                    },
                }
            ],
        }
        lints, hints = linter.lintify_recipe(meta)
        expected = "pin_compatible should be used instead"
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

    def test_rattler_pin_compatible_in_run_exports(self):
        meta = {
            "package": {
                "name": "apackage",
            },
            "requirements": {
                "run_exports": ["pin_compatible apackage"],
            },
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        expected = "pin_subpackage should be used instead"
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

    def test_rattler_pin_compatible_in_run_exports_output(self):
        meta = {
            "package": {
                "name": "apackage",
            },
            "outputs": [
                {
                    "name": "anoutput",
                    "requirements": {
                        "run_exports": ["pin_subpackage notanoutput }}"],
                    },
                }
            ],
        }
        lints, _ = linter.lintify_recipe(meta, is_rattler_build=True)
        expected = "pin_compatible should be used instead"
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

    def test_bad_top_level(self):
        meta = OrderedDict([["package", {}], ["build", {}], ["sources", {}]])
        lints, hints = linter.lintify_recipe(meta)
        expected_msg = "The top level meta key sources is unexpected"
        self.assertIn(expected_msg, lints)

    def test_bad_order(self):
        meta = OrderedDict([["package", {}], ["build", {}], ["source", {}]])
        lints, hints = linter.lintify_recipe(meta)
        expected_msg = (
            "The top level meta keys are in an unexpected "
            "order. Expecting ['package', 'source', 'build']."
        )
        self.assertIn(expected_msg, lints)

    def test_missing_about_license_and_summary(self):
        meta = {"about": {"home": "a URL"}}
        lints, hints = linter.lintify_recipe(meta)
        expected_message = "The license item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The summary item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_bad_about_license(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "unknown",
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        expected_message = "The recipe license cannot be unknown."
        self.assertIn(expected_message, lints)

    def test_bad_about_license_family(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "BSD 3-clause",
                "license_family": "BSD3",
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        expected = "about/license_family 'BSD3' not allowed"
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

    def test_missing_about_home(self):
        meta = {"about": {"license": "BSD", "summary": "A test summary"}}
        lints, hints = linter.lintify_recipe(meta)
        expected_message = "The home item is expected in the about section."
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        expected_message = (
            "The homepage item is expected in the about section."
        )
        self.assertIn(expected_message, lints)

    def test_missing_about_home_empty(self):
        meta = {"about": {"home": "", "summary": "", "license": ""}}
        lints, hints = linter.lintify_recipe(meta)
        expected_message = "The home item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The license item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The summary item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_missing_about_homepage_empty(self):
        meta = {"about": {"homepage": "", "summary": "", "license": ""}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        expected_message = (
            "The homepage item is expected in the about section."
        )
        self.assertIn(expected_message, lints)

        expected_message = "The license item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The summary item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_noarch_value(self):
        """
        for rattler recipe.yaml will be catched by schema
        """
        meta = {"build": {"noarch": "true"}}
        expected = "Invalid `noarch` value `true`. Should be one of"
        lints, hints = linter.lintify_recipe(meta)
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

    def test_maintainers_section(self):
        expected_message = (
            "The recipe could do with some maintainers listed "
            "in the `extra/recipe-maintainers` section."
        )

        lints, hints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": []}}
        )
        self.assertIn(expected_message, lints)

        # No extra section at all.
        lints, hints = linter.lintify_recipe({})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": ["a"]}}
        )
        self.assertNotIn(expected_message, lints)

        expected_message = (
            'The "extra" section was expected to be a '
            "dictionary, but got a list."
        )
        lints, hints = linter.lintify_recipe({"extra": ["recipe-maintainers"]})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": "Luke"}}
        )
        expected_message = "Recipe maintainers should be a json list."
        self.assertIn(expected_message, lints)

    def test_rattler_maintainers_section(self):
        expected_message = (
            "The recipe could do with some maintainers listed "
            "in the `extra/recipe-maintainers` section."
        )

        lints, hints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": []}}, is_rattler_build=True
        )
        self.assertIn(expected_message, lints)

        # No extra section at all.
        lints, hints = linter.lintify_recipe({}, is_rattler_build=True)
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": ["a"]}}, is_rattler_build=True
        )
        self.assertNotIn(expected_message, lints)

    def test_test_section(self):
        expected_message = "The recipe must have some tests."

        lints, hints = linter.lintify_recipe({})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe({"test": {"files": "foo"}})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe({"test": {"imports": "sys"}})
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_recipe({"outputs": [{"name": "foo"}]})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"outputs": [{"name": "foo", "test": {"files": "foo"}}]}
        )
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"outputs": [{"name": "foo", "test": {"imports": "sys"}}]}
        )
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {
                "outputs": [
                    {"name": "foo", "test": {"imports": "sys"}},
                    {"name": "foobar", "test": {"files": "hi"}},
                ]
            }
        )
        self.assertNotIn(expected_message, lints)
        self.assertIn(
            "It looks like the 'foobar' output doesn't have any tests.", hints
        )

        lints, hints = linter.lintify_recipe(
            {
                "outputs": [
                    {"name": "foo", "test": {"script": "test-foo.sh"}},
                    {"name": "foobar", "test": {"script": "test-foobar.pl"}},
                ]
            }
        )
        self.assertNotIn(expected_message, lints)
        self.assertIn(
            "It looks like the 'foobar' output doesn't have any tests.", hints
        )

    def test_rattler_test_section(self):
        expected_message = "The recipe must have some tests."

        lints, hints = linter.lintify_recipe({}, is_rattler_build=True)
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"tests": {"script": "sys"}}, is_rattler_build=True
        )
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"outputs": [{"name": "foo"}]}, is_rattler_build=True
        )
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"outputs": [{"name": "foo", "tests": {"python": "sys"}}]},
            is_rattler_build=True,
        )
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {
                "outputs": [
                    {"name": "foo", "tests": {"script": "sys"}},
                    {
                        "name": "foobar",
                    },
                ]
            },
            is_rattler_build=True,
        )
        self.assertNotIn(expected_message, lints)
        self.assertIn(
            "It looks like the 'foobar' output doesn't have any tests.", hints
        )

    def test_test_section_with_recipe(self):
        # If we have a run_test.py file, we shouldn't need to provide
        # other tests.

        expected_message = "The recipe must have some tests."

        with tmp_directory() as recipe_dir:
            lints, hints = linter.lintify_recipe({}, recipe_dir)
            self.assertIn(expected_message, lints)

            with io.open(os.path.join(recipe_dir, "run_test.py"), "w") as fh:
                fh.write("# foo")
            lints, hints = linter.lintify_recipe({}, recipe_dir)
            self.assertNotIn(expected_message, lints)

    def test_jinja2_vars(self):
        expected_message = (
            "Jinja2 variable references are suggested to take a ``{{<one space>"
            "<variable name><one space>}}`` form. See lines %s."
            % ([6, 8, 10, 11, 12])
        )

        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                    package:
                       name: foo
                    requirements:
                      run:
                        - {{name}}
                        - {{ x.update({4:5}) }}
                        - {{ name}}
                        - {{ name }}
                        - {{name|lower}}
                        - {{ name|lower}}
                        - {{name|lower }}
                        - {{ name|lower }}
                    """
                )

            _, hints = linter.lintify_recipe({}, recipe_dir)
            self.assertTrue(any(h.startswith(expected_message) for h in hints))

    def test_rattler_jinja2_vars(self):
        expected_message = (
            "Jinja2 variable references are suggested to take a ``${{<one space>"
            "<variable name><one space>}}`` form. See lines %s."
            % ([6, 8, 10, 11, 12])
        )

        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
                fh.write(
                    """
                    package:
                       name: foo
                    requirements:
                      run:
                        - ${{name}}
                        - ${{ x.update({4:5}) }}
                        - ${{ name}}
                        - ${{ name }}
                        - ${{name|lower}}
                        - ${{ name|lower}}
                        - ${{name|lower }}
                        - ${{ name|lower }}
                    """
                )

            _, hints = linter.lintify_recipe(
                {}, recipe_dir, is_rattler_build=True
            )
            self.assertTrue(any(h.startswith(expected_message) for h in hints))

    def test_selectors(self):
        expected_message = (
            "Selectors are suggested to take a "
            "``<two spaces>#<one space>[<expression>]`` form."
            " See lines {}".format([3])
        )

        with tmp_directory() as recipe_dir:

            def assert_selector(selector, is_good=True):
                with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(
                        """
                            package:
                               name: foo_py2  # [py2k]
                               {}
                             """.format(
                            selector
                        )
                    )
                lints, hints = linter.lintify_recipe({}, recipe_dir)
                if is_good:
                    message = (
                        "Found lints when there shouldn't have been a "
                        "lint for '{}'.".format(selector)
                    )
                else:
                    message = (
                        "Expecting lints for '{}', but didn't get any."
                        "".format(selector)
                    )
                self.assertEqual(
                    not is_good,
                    any(lint.startswith(expected_message) for lint in lints),
                    message,
                )

            assert_selector("name: foo_py3      # [py3k]")
            assert_selector("name: foo_py3  [py3k]", is_good=False)
            assert_selector("name: foo_py3  #[py3k]", is_good=False)
            assert_selector("name: foo_py3 # [py3k]", is_good=False)

    def test_pyXY_selectors(self):
        with tmp_directory() as recipe_dir:

            def assert_pyXY_selector(meta_string, is_good=False, kind="lint"):
                assert kind in ("lint", "hint")
                if kind == "hint":
                    expected_start = "Old-style Python selectors (py27, py34, py35, py36) are deprecated"
                else:
                    expected_start = "Old-style Python selectors (py27, py35, etc) are only available"
                with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(meta_string)
                lints, hints = linter.main(recipe_dir, return_hints=True)
                if is_good:
                    message = (
                        "Found lints or hints when there shouldn't have "
                        "been for '{}'."
                    ).format(meta_string)
                else:
                    message = (
                        "Expected lints or hints for '{}', but didn't get any."
                    ).format(meta_string)
                problems = lints if kind == "lint" else hints
                self.assertEqual(
                    not is_good,
                    any(
                        problem.startswith(expected_start)
                        for problem in problems
                    ),
                    message,
                )

            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [py27]
                            """,
                kind="hint",
            )
            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [py310]
                            """,
                kind="lint",
            )
            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [py38]
                            """,
                kind="lint",
            )
            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"   #   [py36]
                            """,
                kind="hint",
            )
            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [win or py37]
                            """,
                kind="lint",
            )
            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [py37 or win]
                            """,
                kind="lint",
            )
            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [unix or py37 or win]
                            """,
                kind="lint",
            )
            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [unix or py37 or py27]
                            """,
                kind="lint",
            )
            assert_pyXY_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [py==37]
                            """,
                is_good=True,
            )

    def test_noarch_selectors(self):
        expected_start = "`noarch` packages can't have"

        with tmp_directory() as recipe_dir:

            def assert_noarch_selector(meta_string, is_good=False):
                with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(meta_string)
                lints = linter.main(recipe_dir)
                if is_good:
                    message = (
                        "Found lints when there shouldn't have "
                        "been a lint for '{}'."
                    ).format(meta_string)
                else:
                    message = (
                        "Expected lints for '{}', but didn't " "get any."
                    ).format(meta_string)
                self.assertEqual(
                    not is_good,
                    any(lint.startswith(expected_start) for lint in lints),
                    message,
                )

            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              skip: true  # [py2k]
                            """
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: generic
                              skip: true  # [win]
                            """
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              skip: true  #
                            """,
                is_good=True,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [unix]
                                - echo "hello" # [win]
                            """,
                is_good=True,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [unix]
                                - echo "hello" # [win]
                              requirements:
                                build:
                                  - python
                            """,
                is_good=True,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [unix]
                                - echo "hello" # [win]
                              requirements:
                                build:
                                  - python
                                host: # empty sections are allowed and ignored
                                run: # empty sections are allowed and ignored
                              tests:
                                commands:
                                  - cp asd qwe  # [unix]
                            """,
                is_good=True,
            )
            assert_noarch_selector(
                """
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
                            """,
                is_good=True,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              requirements:
                                build: # empty sections are allowed and ignored
                                run:
                                  - python
                                  - enum34     # [py2k]
                            """
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              requirements:
                                host:
                                  - python
                                  - enum34     # [py2k]
                            """
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              requirements:
                                host:
                                  - enum34     # [py2k]
                                run:
                                  - python
                            """
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              requirements:
                                host:
                                  - python
                                run:
                                  - enum34     # [py2k]
                            """
            )

    def test_rattler_noarch_selectors(self):
        expected_start = "`noarch` packages can't have"

        with tmp_directory() as recipe_dir:

            def assert_noarch_selector(meta_string, is_good=False):
                with io.open(
                    os.path.join(recipe_dir, "recipe.yaml"), "w"
                ) as fh:
                    fh.write(meta_string)

                with io.open(
                    os.path.join(recipe_dir, "conda-forge.yml"), "w"
                ) as fh:
                    fh.write("conda_build_tool: rattler-build")

                lints = linter.main(recipe_dir, feedstock_dir=recipe_dir)
                if is_good:
                    message = (
                        "Found lints when there shouldn't have "
                        "been a lint for '{}'."
                    ).format(meta_string)
                else:
                    message = (
                        "Expected lints for '{}', but didn't " "get any."
                    ).format(meta_string)
                self.assertEqual(
                    not is_good,
                    any(lint.startswith(expected_start) for lint in lints),
                    message,
                )

            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              skip:
                                - win
                """
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                            """,
                is_good=True,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              requirements:
                                build:
                                  - python
                            """,
                is_good=True,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [unix]
                                - echo "hello" # [win]
                              requirements:
                                build:
                                  - python
                                  - if win:
                                    then:
                                     - enum34
                            """,
                is_good=True,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                            requirements:
                                run:
                                  - python
                                  - if win:
                                    then:
                                      - enum34
                            """
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                            requirements:
                              host:
                                - python
                                - if win:
                                  then:
                                  - enum34
                            """
            )

    def test_suggest_noarch(self):
        expected_start = "Whenever possible python packages should use noarch."

        with tmp_directory() as recipe_dir:

            def assert_noarch_hint(meta_string, is_good=False):
                with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(meta_string)
                lints, hints = linter.main(recipe_dir, return_hints=True)
                if is_good:
                    message = (
                        "Found hints when there shouldn't have "
                        "been a lint for '{}'."
                    ).format(meta_string)
                else:
                    message = (
                        "Expected hints for '{}', but didn't " "get any."
                    ).format(meta_string)
                self.assertEqual(
                    not is_good,
                    any(lint.startswith(expected_start) for lint in hints),
                    message,
                )

            assert_noarch_hint(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"
                            requirements:
                              build:
                                - python
                                - pip
                            """,
                is_good=True,
            )
            assert_noarch_hint(
                """
                            build:
                              script:
                                - echo "hello"
                            requirements:
                              build:
                                - python
                                - pip
                            """
            )
            assert_noarch_hint(
                """
                            build:
                              script:
                                - echo "hello"
                            requirements:
                              build:
                                - python
                            """,
                is_good=True,
            )
            assert_noarch_hint(
                """
                            build:
                              script:
                                - echo "hello"
                            requirements:
                              build:
                                - python
                                - {{ compiler('c') }}
                                - pip
                            """,
                is_good=True,
            )

    def test_suggest_rattler_noarch(self):
        expected_start = "Whenever possible python packages should use noarch."
        with tmp_directory() as recipe_dir:

            def assert_noarch_hint(meta_string, is_good=False):
                with io.open(
                    os.path.join(recipe_dir, "recipe.yaml"), "w"
                ) as fh:
                    fh.write(meta_string)

                with io.open(
                    os.path.join(recipe_dir, "conda-forge.yml"), "w"
                ) as fh:
                    fh.write("conda_build_tool: rattler-build")

                lints, hints = linter.main(
                    recipe_dir, return_hints=True, feedstock_dir=recipe_dir
                )
                if is_good:
                    message = (
                        "Found hints when there shouldn't have "
                        "been a hint for '{}'."
                    ).format(meta_string)
                else:
                    message = (
                        "Expected hints for '{}', but didn't " "get any."
                    ).format(meta_string)
                self.assertEqual(
                    not is_good,
                    any(lint.startswith(expected_start) for lint in hints),
                    message,
                )

            assert_noarch_hint(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"
                            requirements:
                              build:
                                - python
                                - pip
                            """,
                is_good=True,
            )
            assert_noarch_hint(
                """
                            build:
                              script:
                                - echo "hello"
                            requirements:
                              build:
                                - python
                                - pip
                            """
            )
            assert_noarch_hint(
                """
                            build:
                              script:
                                - echo "hello"
                            requirements:
                              build:
                                - python
                            """,
                is_good=True,
            )
            assert_noarch_hint(
                """
                            build:
                              script:
                                - echo "hello"
                            requirements:
                              build:
                                - python
                                - ${{ compiler('c') }}
                                - pip
                            """,
                is_good=True,
            )

    def test_jinja_os_environ(self):
        # Test that we can use os.environ in a recipe. We don't care about
        # the results here.
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set version = os.environ.get('WIBBLE') %}
                        package:
                           name: foo
                           version: {{ version }}
                         """
                )
            lints = linter.main(recipe_dir)

    def test_jinja_load_file_regex(self):
        # Test that we can use load_file_regex in a recipe. We don't care about
        # the results here.
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "sha256"), "w") as fh:
                fh.write(
                    """
                        d0e46ea5fca7d4c077245fe0b4195a828d9d4d69be8a0bd46233b2c12abd2098  iwftc_osx.zip
                        8ce4dc535b21484f65027be56263d8b0d9f58e57532614e1a8f6881f3b8fe260  iwftc_win.zip
                        """
                )
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set sha256_osx = load_file_regex(load_file="sha256",
                                                        regex_pattern="(?m)^(?P<sha256>[0-9a-f]+)\\s+iwftc_osx.zip$",
                                                        from_recipe_dir=True)["sha256"] %}
                        package:
                          name: foo
                          version: {{ version }}
                        """
                )
            lints = linter.main(recipe_dir)

    def test_jinja_load_file_data(self):
        # Test that we can use load_file_data in a recipe. We don't care about
        # the results here and/or the actual file data because the recipe linter
        # renders conda-build functions to just function stubs to pass the linting.
        # TODO: add *args and **kwargs for functions used to parse the file.
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set data = load_file_data("IDONTNEED", from_recipe_dir=True, recipe_dir=".") %}
                        package:
                          name: foo
                          version: {{ version }}
                        """
                )
            lints = linter.main(recipe_dir)

    def test_jinja_load_setup_py_data(self):
        # Test that we can use load_setup_py_data in a recipe. We don't care about
        # the results here and/or the actual file data because the recipe linter
        # renders conda-build functions to just function stubs to pass the linting.
        # TODO: add *args and **kwargs for functions used to parse the file.
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set data = load_setup_py_data("IDONTNEED", from_recipe_dir=True, recipe_dir=".") %}
                        package:
                          name: foo
                          version: {{ version }}
                        """
                )
            lints = linter.main(recipe_dir)

    def test_jinja_load_str_data(self):
        # Test that we can use load_str_data in a recipe. We don't care about
        # the results here and/or the actual file data because the recipe linter
        # renders conda-build functions to just function stubs to pass the linting.
        # TODO: add *args and **kwargs for functions used to parse the data.
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set data = load_str_data("IDONTNEED", "json") %}
                        package:
                          name: foo
                          version: {{ version }}
                        """
                )
            lints = linter.main(recipe_dir)

    def test_jinja_os_sep(self):
        # Test that we can use os.sep in a recipe.
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        package:
                           name: foo_
                           version: 1.0
                        build:
                          script: {{ os.sep }}
                         """
                )
            lints = linter.main(recipe_dir)

    def test_target_platform(self):
        # Test that we can use target_platform in a recipe. We don't care about
        # the results here.
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        package:
                           name: foo_{{ target_platform }}
                           version: 1.0
                         """
                )
            lints = linter.main(recipe_dir)

    def test_missing_build_number(self):
        expected_message = "The recipe must have a `build/number` section."

        meta = {
            "build": {
                "skip": "True",
                "script": "python setup.py install",
                "number": 0,
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(expected_message, lints)

        meta = {"build": {"skip": "True", "script": "python setup.py install"}}
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(expected_message, lints)

    def test_rattler_missing_build_number(self):
        expected_message = "The recipe must have a `build/number` section."

        meta = {
            "build": {
                "skip": "True",
                "script": "python setup.py install",
                "number": 0,
            }
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(expected_message, lints)

        meta = {"build": {"skip": "True", "script": "python setup.py install"}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(expected_message, lints)

    def test_bad_requirements_order(self):
        expected_message = (
            "The `requirements/` sections should be defined in "
            "the following order: build, host, run; "
            "instead saw: run, build."
        )

        meta = {
            "requirements": OrderedDict([["run", ["a"]], ["build", ["a"]]])
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(expected_message, lints)

        meta = {
            "requirements": OrderedDict(
                [["run", ["a"]], ["invalid", ["a"]], ["build", ["a"]]]
            )
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(expected_message, lints)

        meta = {
            "requirements": OrderedDict([["build", ["a"]], ["run", ["a"]]])
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(expected_message, lints)

    def test_rattler_bad_requirements_order(self):
        expected_message = (
            "The `requirements/` sections should be defined in "
            "the following order: build, host, run; "
            "instead saw: run, build."
        )

        meta = {"requirements": OrderedDict([["run", "a"], ["build", "a"]])}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(expected_message, lints)

        meta = {
            "requirements": OrderedDict(
                [["run", "a"], ["invalid", "a"], ["build", "a"]]
            )
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(expected_message, lints)

        meta = {"requirements": OrderedDict([["build", "a"], ["run", "a"]])}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(expected_message, lints)

    def test_noarch_python_bound(self):
        expected_message = (
            "noarch: python recipes are required to have a lower bound "
            "on the python version. Typically this means putting "
            "`python >=3.6` in **both** `host` and `run` but you should check "
            "upstream for the package's Python compatibility."
        )
        meta = {
            "build": {"noarch": "python"},
            "requirements": {
                "host": [
                    "python",
                ],
                "run": [
                    "python",
                ],
            },
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(expected_message, lints)

        meta = {
            "build": {"noarch": "python"},
            "requirements": {
                "host": [
                    "python",
                ],
                "run": [
                    "python >=2.7",
                ],
            },
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(expected_message, lints)

        meta = {
            "build": {"noarch": "generic"},
            "requirements": {
                "host": [
                    "python",
                ],
                "run": [
                    "python",
                ],
            },
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(expected_message, lints)

    def test_rattler_noarch_python_bound(self):
        expected_message = (
            "noarch: python recipes are required to have a lower bound "
            "on the python version. Typically this means putting "
            "`python >=3.6` in **both** `host` and `run` but you should check "
            "upstream for the package's Python compatibility."
        )
        meta = {
            "build": {"noarch": "python"},
            "requirements": {
                "host": [
                    "python",
                ],
                "run": [
                    "python",
                ],
            },
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(expected_message, lints)

        meta = {
            "build": {"noarch": "python"},
            "requirements": {
                "host": [
                    "python",
                ],
                "run": [
                    "python >=2.7",
                ],
            },
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(expected_message, lints)

        meta = {
            "build": {"noarch": "generic"},
            "requirements": {
                "host": [
                    "python",
                ],
                "run": [
                    "python",
                ],
            },
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(expected_message, lints)

    def test_no_sha_with_dl(self):
        expected_message = (
            "When defining a source/url please add a sha256, "
            "sha1 or md5 checksum (sha256 preferably)."
        )
        lints, hints = linter.lintify_recipe({"source": {"url": None}})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"source": {"url": None, "sha1": None}}
        )
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"source": {"url": None, "sha256": None}}
        )
        self.assertNotIn(expected_message, lints, hints)

        meta = {"source": {"url": None, "md5": None}}
        self.assertNotIn(expected_message, linter.lintify_recipe(meta))

    def test_rattler_no_sha_with_dl(self):
        expected_message = (
            "When defining a source/url please add a sha256, "
            "sha1 or md5 checksum (sha256 preferably)."
        )
        lints, hints = linter.lintify_recipe(
            {"source": {"url": None}}, is_rattler_build=True
        )
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"source": {"url": None, "sha1": None}}, is_rattler_build=True
        )
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_recipe(
            {"source": {"url": None, "sha256": None}}, is_rattler_build=True
        )
        self.assertNotIn(expected_message, lints, hints)

        meta = {"source": {"url": None, "md5": None}}
        self.assertNotIn(
            expected_message,
            linter.lintify_recipe(meta, is_rattler_build=True),
        )

    def test_redundant_license(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "MIT License",
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        expected_message = (
            "The recipe `license` should not include " 'the word "License".'
        )
        self.assertIn(expected_message, lints)

    def test_rattler_redundant_license(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "MIT License",
            }
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        expected_message = (
            "The recipe `license` should not include " 'the word "License".'
        )
        self.assertIn(expected_message, lints)

    def test_spdx_license(self):
        msg = (
            "License is not an SPDX identifier (or a custom LicenseRef) nor an SPDX license expression.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )
        licenses = {
            "BSD-100": False,
            "GPL-2.0": False,
            "GPL-2.0-only": True,
            "Other": False,
            "GPL-2.0-or-later or MIT": True,
            "LGPL-2.0-only | MIT": False,
            "LLVM-exception": False,
            "LicenseRef-kebab-case-2--with.dots OR MIT": True,
            "LicenseRef-HDF5": True,
            "LicenseRef-@HDF5": False,
        }
        for license, good in licenses.items():
            meta = {"about": {"license": license}}
            lints, hints = linter.lintify_recipe(meta)
            print(license, good)
            if good:
                self.assertNotIn(msg, hints)
            else:
                self.assertIn(msg, hints)

    def test_rattler_spdx_license(self):
        msg = (
            "License is not an SPDX identifier (or a custom LicenseRef) nor an SPDX license expression.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )
        licenses = {
            "BSD-100": False,
            "GPL-2.0": False,
            "GPL-2.0-only": True,
            "Other": False,
            "GPL-2.0-or-later or MIT": True,
            "LGPL-2.0-only | MIT": False,
            "LLVM-exception": False,
            "LicenseRef-kebab-case-2--with.dots OR MIT": True,
            "LicenseRef-HDF5": True,
            "LicenseRef-@HDF5": False,
        }
        for license, good in licenses.items():
            meta = {"about": {"license": license}}
            lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
            print(license, good)
            if good:
                self.assertNotIn(msg, hints)
            else:
                self.assertIn(msg, hints)

    def test_spdx_license_exception(self):
        msg = (
            "License exception is not an SPDX exception.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )
        licenses = {
            "Apache 2.0 WITH LLVM-exception": True,
            "Apache 2.0 WITH LLVM2-exception": False,
        }
        for license, good in licenses.items():
            meta = {"about": {"license": license}}
            lints, hints = linter.lintify_recipe(meta)
            if good:
                self.assertNotIn(msg, hints)
            else:
                self.assertIn(msg, hints)

    def test_rattler_spdx_license_exception(self):
        msg = (
            "License exception is not an SPDX exception.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )
        licenses = {
            "Apache 2.0 WITH LLVM-exception": True,
            "Apache 2.0 WITH LLVM2-exception": False,
        }
        for license, good in licenses.items():
            meta = {"about": {"license": license}}
            lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
            if good:
                self.assertNotIn(msg, hints)
            else:
                self.assertIn(msg, hints)

    def test_license_file_required(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "MIT",
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        expected_message = "license_file entry is missing, but is required."
        self.assertIn(expected_message, lints)

    def test_rattler_license_file_required(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "MIT",
            }
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        expected_message = "license_file entry is missing, but is required."
        self.assertIn(expected_message, lints)

    def test_license_file_empty(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "LicenseRef-Something",
                "license_family": "LGPL",
                "license_file": None,
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        expected_message = "license_file entry is missing, but is required."
        self.assertIn(expected_message, lints)

    def test_rattler_license_file_empty(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "LicenseRef-Something",
                "license_file": None,
            }
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        expected_message = "license_file entry is missing, but is required."
        self.assertIn(expected_message, lints)

    def test_recipe_name(self):
        meta = {"package": {"name": "mp++"}}
        lints, hints = linter.lintify_recipe(meta)
        expected_message = (
            "Recipe name has invalid characters. only lowercase alpha, "
            "numeric, underscores, hyphens and dots allowed"
        )
        self.assertIn(expected_message, lints)

    def test_rattler_recipe_name(self):
        meta = {"package": {"name": "mp++"}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        expected_message = (
            "Recipe name has invalid characters. only lowercase alpha, "
            "numeric, underscores, hyphens and dots allowed"
        )
        self.assertIn(expected_message, lints)

    def test_end_empty_line(self):
        bad_contents = [
            # No empty lines at the end of the file
            "extra:\n  recipe-maintainers:\n    - goanpeca",
            "extra:\r  recipe-maintainers:\r    - goanpeca",
            "extra:\r\n  recipe-maintainers:\r\n    - goanpeca",
            # Two empty lines at the end of the file
            "extra:\n  recipe-maintainers:\n    - goanpeca\n\n",
            "extra:\r  recipe-maintainers:\r    - goanpeca\r\r",
            "extra:\r\n  recipe-maintainers:\r\n    - goanpeca\r\n\r\n",
            # Three empty lines at the end of the file
            "extra:\n  recipe-maintainers:\n    - goanpeca\n\n\n",
            "extra:\r  recipe-maintainers:\r    - goanpeca\r\r\r",
            "extra:\r\n  recipe-maintainers:\r\n    - goanpeca\r\n\r\n\r\n",
        ]
        # Exactly one empty line at the end of the file
        valid_content = "extra:\n  recipe-maintainers:\n    - goanpeca\n"

        for content, lines in zip(
            bad_contents + [valid_content], [0, 0, 0, 2, 2, 2, 3, 3, 3, 1]
        ):
            with tmp_directory() as recipe_dir:
                with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as f:
                    f.write(content)
                lints, hints = linter.lintify_recipe({}, recipe_dir=recipe_dir)
                if lines > 1:
                    expected_message = (
                        "There are {} too many lines.  "
                        "There should be one empty line "
                        "at the end of the "
                        "file.".format(lines - 1)
                    )
                else:
                    expected_message = (
                        "There are too few lines.  "
                        "There should be one empty line at"
                        " the end of the file."
                    )
                if content == valid_content:
                    self.assertNotIn(expected_message, lints)
                else:
                    self.assertIn(expected_message, lints)

    def test_rattler_end_empty_line(self):
        bad_contents = [
            # No empty lines at the end of the file
            "extra:\n  recipe-maintainers:\n    - goanpeca",
            "extra:\r  recipe-maintainers:\r    - goanpeca",
            "extra:\r\n  recipe-maintainers:\r\n    - goanpeca",
            # Two empty lines at the end of the file
            "extra:\n  recipe-maintainers:\n    - goanpeca\n\n",
            "extra:\r  recipe-maintainers:\r    - goanpeca\r\r",
            "extra:\r\n  recipe-maintainers:\r\n    - goanpeca\r\n\r\n",
            # Three empty lines at the end of the file
            "extra:\n  recipe-maintainers:\n    - goanpeca\n\n\n",
            "extra:\r  recipe-maintainers:\r    - goanpeca\r\r\r",
            "extra:\r\n  recipe-maintainers:\r\n    - goanpeca\r\n\r\n\r\n",
        ]
        # Exactly one empty line at the end of the file
        valid_content = "extra:\n  recipe-maintainers:\n    - goanpeca\n"

        for content, lines in zip(
            bad_contents + [valid_content], [0, 0, 0, 2, 2, 2, 3, 3, 3, 1]
        ):
            with tmp_directory() as recipe_dir:
                with io.open(
                    os.path.join(recipe_dir, "recipe.yaml"), "w"
                ) as f:
                    f.write(content)
                lints, hints = linter.lintify_recipe(
                    {}, recipe_dir=recipe_dir, is_rattler_build=True
                )
                if lines > 1:
                    expected_message = (
                        "There are {} too many lines.  "
                        "There should be one empty line "
                        "at the end of the "
                        "file.".format(lines - 1)
                    )
                else:
                    expected_message = (
                        "There are too few lines.  "
                        "There should be one empty line at"
                        " the end of the file."
                    )
                if content == valid_content:
                    self.assertNotIn(expected_message, lints)
                else:
                    self.assertIn(expected_message, lints)

    def test_cb3_jinja2_functions(self):
        lints = linter.main(
            os.path.join(
                _thisdir, "recipes", "cb3_jinja2_functions", "recipe"
            ),
        )
        assert not lints

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_maintainer_exists(self):
        lints, _ = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": ["support"]}}, conda_forge=True
        )
        expected_message = 'Recipe maintainer "support" does not exist'
        self.assertIn(expected_message, lints)

        lints, _ = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": ["isuruf"]}}, conda_forge=True
        )
        expected_message = 'Recipe maintainer "isuruf" does not exist'
        self.assertNotIn(expected_message, lints)

        expected_message = (
            "Feedstock with the same name exists in conda-forge."
        )
        # Check that feedstock exists if staged_recipes
        lints, _ = linter.lintify_recipe(
            {"package": {"name": "python"}},
            recipe_dir="python",
            conda_forge=True,
        )
        self.assertIn(expected_message, lints)
        lints, _ = linter.lintify_recipe(
            {"package": {"name": "python"}},
            recipe_dir="python",
            conda_forge=False,
        )
        self.assertNotIn(expected_message, lints)
        # No lint if in a feedstock
        lints, _ = linter.lintify_recipe(
            {"package": {"name": "python"}},
            recipe_dir="recipe",
            conda_forge=True,
        )
        self.assertNotIn(expected_message, lints)
        lints, _ = linter.lintify_recipe(
            {"package": {"name": "python"}},
            recipe_dir="recipe",
            conda_forge=False,
        )
        self.assertNotIn(expected_message, lints)

        # Make sure there's no feedstock named python1 before proceeding
        gh = github.Github(os.environ["GH_TOKEN"])
        cf = gh.get_user("conda-forge")
        try:
            cf.get_repo("python1-feedstock")
            feedstock_exists = True
        except github.UnknownObjectException as e:
            feedstock_exists = False

        if feedstock_exists:
            warnings.warn(
                "There's a feedstock named python1, but tests assume that there isn't"
            )
        else:
            lints, _ = linter.lintify_recipe(
                {"package": {"name": "python1"}},
                recipe_dir="python",
                conda_forge=True,
            )
            self.assertNotIn(expected_message, lints)

        # Test bioconda recipe checking
        expected_message = (
            "Recipe with the same name exists in bioconda: "
            "please discuss with @conda-forge/bioconda-recipes."
        )
        bio = gh.get_user("bioconda").get_repo("bioconda-recipes")
        r = "samtools"
        try:
            bio.get_dir_contents("recipe/{}".format(r))
        except github.UnknownObjectException as e:
            warnings.warn(
                "There's no bioconda recipe named {}, but tests assume that there is".format(
                    r
                )
            )
        else:
            # Check that feedstock exists if staged_recipes
            lints, _ = linter.lintify_recipe(
                {"package": {"name": r}}, recipe_dir=r, conda_forge=True
            )
            self.assertIn(expected_message, lints)
            lints, _ = linter.lintify_recipe(
                {"package": {"name": r}}, recipe_dir=r, conda_forge=False
            )
            self.assertNotIn(expected_message, lints)
            # No lint if in a feedstock
            lints, _ = linter.lintify_recipe(
                {"package": {"name": r}}, recipe_dir="recipe", conda_forge=True
            )
            self.assertNotIn(expected_message, lints)
            lints, _ = linter.lintify_recipe(
                {"package": {"name": r}},
                recipe_dir="recipe",
                conda_forge=False,
            )
            self.assertNotIn(expected_message, lints)
            # No lint if the name isn't specified
            lints, _ = linter.lintify_recipe(
                {}, recipe_dir=r, conda_forge=True
            )
            self.assertNotIn(expected_message, lints)

        r = "this-will-never-exist"
        try:
            bio.get_dir_contents("recipes/{}".format(r))
        except github.UnknownObjectException as e:
            lints, _ = linter.lintify_recipe(
                {"package": {"name": r}}, recipe_dir=r, conda_forge=True
            )
            self.assertNotIn(expected_message, lints)
        else:
            warnings.warn(
                "There's a bioconda recipe named {}, but tests assume that there isn't".format(
                    r
                )
            )

        expected_message = (
            "A conda package with same name (numpy) already exists."
        )
        lints, hints = linter.lintify_recipe(
            {
                "package": {"name": "this-will-never-exist"},
                "source": {
                    "url": "https://pypi.io/packages/source/n/numpy/numpy-1.26.4.tar.gz"
                },
            },
            recipe_dir="recipes/foo",
            conda_forge=True,
        )
        self.assertIn(expected_message, hints)

        # check that this doesn't choke
        lints, hints = linter.lintify_recipe(
            {
                "package": {"name": "this-will-never-exist"},
                "source": {
                    "url": [
                        "https://pypi.io/packages/source/f/fitsio/fitsio-v0.9.2.tar.gz"
                    ]
                },
            },
            recipe_dir="recipes/foo",
            conda_forge=True,
        )

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_rattler_maintainer_exists(self):
        lints, _ = linter.lintify_recipe, is_rattler_build = True(
            {"extra": {"recipe-maintainers": ["support"]}}, conda_forge=True
        )
        expected_message = 'Recipe maintainer "support" does not exist'
        self.assertIn(expected_message, lints)

        lints, _ = linter.lintify_recipe, is_rattler_build = True(
            {"extra": {"recipe-maintainers": ["isuruf"]}}, conda_forge=True
        )
        expected_message = 'Recipe maintainer "isuruf" does not exist'
        self.assertNotIn(expected_message, lints)

        expected_message = (
            "Feedstock with the same name exists in conda-forge."
        )
        # Check that feedstock exists if staged_recipes
        lints, _ = linter.lintify_recipe, is_rattler_build = True(
            {"package": {"name": "python"}},
            recipe_dir="python",
            conda_forge=True,
        )
        self.assertIn(expected_message, lints)
        lints, _ = linter.lintify_recipe, is_rattler_build = True(
            {"package": {"name": "python"}},
            recipe_dir="python",
            conda_forge=False,
        )
        self.assertNotIn(expected_message, lints)
        # No lint if in a feedstock
        lints, _ = linter.lintify_recipe, is_rattler_build = True(
            {"package": {"name": "python"}},
            recipe_dir="recipe",
            conda_forge=True,
        )
        self.assertNotIn(expected_message, lints)
        lints, _ = linter.lintify_recipe, is_rattler_build = True(
            {"package": {"name": "python"}},
            recipe_dir="recipe",
            conda_forge=False,
        )
        self.assertNotIn(expected_message, lints)

        # Make sure there's no feedstock named python1 before proceeding
        gh = github.Github(os.environ["GH_TOKEN"])
        cf = gh.get_user("conda-forge")
        try:
            cf.get_repo("python1-feedstock")
            feedstock_exists = True
        except github.UnknownObjectException as e:
            feedstock_exists = False

        if feedstock_exists:
            warnings.warn(
                "There's a feedstock named python1, but tests assume that there isn't"
            )
        else:
            lints, _ = linter.lintify_recipe, is_rattler_build = True(
                {"package": {"name": "python1"}},
                recipe_dir="python",
                conda_forge=True,
            )
            self.assertNotIn(expected_message, lints)

        # Test bioconda recipe checking
        expected_message = (
            "Recipe with the same name exists in bioconda: "
            "please discuss with @conda-forge/bioconda-recipes."
        )
        bio = gh.get_user("bioconda").get_repo("bioconda-recipes")
        r = "samtools"
        try:
            bio.get_dir_contents("recipe/{}".format(r))
        except github.UnknownObjectException as e:
            warnings.warn(
                "There's no bioconda recipe named {}, but tests assume that there is".format(
                    r
                )
            )
        else:
            # Check that feedstock exists if staged_recipes
            lints, _ = linter.lintify_recipe, is_rattler_build = True(
                {"package": {"name": r}}, recipe_dir=r, conda_forge=True
            )
            self.assertIn(expected_message, lints)
            lints, _ = linter.lintify_recipe, is_rattler_build = True(
                {"package": {"name": r}}, recipe_dir=r, conda_forge=False
            )
            self.assertNotIn(expected_message, lints)
            # No lint if in a feedstock
            lints, _ = linter.lintify_recipe, is_rattler_build = True(
                {"package": {"name": r}}, recipe_dir="recipe", conda_forge=True
            )
            self.assertNotIn(expected_message, lints)
            lints, _ = linter.lintify_recipe, is_rattler_build = True(
                {"package": {"name": r}},
                recipe_dir="recipe",
                conda_forge=False,
            )
            self.assertNotIn(expected_message, lints)
            # No lint if the name isn't specified
            lints, _ = linter.lintify_recipe, is_rattler_build = True(
                {}, recipe_dir=r, conda_forge=True
            )
            self.assertNotIn(expected_message, lints)

        r = "this-will-never-exist"
        try:
            bio.get_dir_contents("recipes/{}".format(r))
        except github.UnknownObjectException as e:
            lints, _ = linter.lintify_recipe, is_rattler_build = True(
                {"package": {"name": r}}, recipe_dir=r, conda_forge=True
            )
            self.assertNotIn(expected_message, lints)
        else:
            warnings.warn(
                "There's a bioconda recipe named {}, but tests assume that there isn't".format(
                    r
                )
            )

        expected_message = (
            "A conda package with same name (fitsio) already exists."
        )
        lints, hints = linter.lintify_recipe, is_rattler_build = True(
            {
                "package": {"name": "this-will-never-exist"},
                "source": {
                    "url": "https://pypi.io/packages/source/f/fitsio/fitsio-v0.9.2.tar.gz"
                },
            },
            recipe_dir="recipes/foo",
            conda_forge=True,
        )
        self.assertIn(expected_message, hints)

        # check that this doesn't choke
        lints, hints = linter.lintify_recipe, is_rattler_build = True(
            {
                "package": {"name": "this-will-never-exist"},
                "source": {
                    "url": [
                        "https://pypi.io/packages/source/f/fitsio/fitsio-v0.9.2.tar.gz"
                    ]
                },
            },
            recipe_dir="recipes/foo",
            conda_forge=True,
        )

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_maintainer_participation(self):
        # Mocking PR and maintainer data
        os.environ["STAGED_RECIPES_PR_NUMBER"] = "1"  # Example PR number
        maintainers = ["pelson", "isuruf"]

        try:
            # Running the linter function
            lints, _ = linter.lintify_recipe(
                {"extra": {"recipe-maintainers": maintainers}},
                recipe_dir="python",
                conda_forge=True,
            )

            # Expected message if a maintainer has not participated
            expected_message = (
                "The following maintainers have not yet confirmed that they are willing to be listed here: "
                "isuruf. Please ask them to comment on this PR if they are."
            )
            self.assertIn(expected_message, lints)

            expected_message = (
                "The following maintainers have not yet confirmed that they are willing to be listed here: "
                "pelson, isuruf. Please ask them to comment on this PR if they are."
            )
            self.assertNotIn(expected_message, lints)
        finally:
            del os.environ["STAGED_RECIPES_PR_NUMBER"]

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_rattler_maintainer_participation(self):
        # Mocking PR and maintainer data
        os.environ["STAGED_RECIPES_PR_NUMBER"] = "1"  # Example PR number
        maintainers = ["pelson", "isuruf"]

        try:
            # Running the linter function
            lints, _ = linter.lintify_recipe, is_rattler_build = True(
                {"extra": {"recipe-maintainers": maintainers}},
                recipe_dir="python",
                conda_forge=True,
            )

            # Expected message if a maintainer has not participated
            expected_message = (
                "The following maintainers have not yet confirmed that they are willing to be listed here: "
                "isuruf. Please ask them to comment on this PR if they are."
            )
            self.assertIn(expected_message, lints)

            expected_message = (
                "The following maintainers have not yet confirmed that they are willing to be listed here: "
                "pelson, isuruf. Please ask them to comment on this PR if they are."
            )
            self.assertNotIn(expected_message, lints)
        finally:
            del os.environ["STAGED_RECIPES_PR_NUMBER"]

    def test_bad_subheader(self):
        expected_message = (
            "The {} section contained an unexpected "
            "subsection name. {} is not a valid subsection"
            " name."
        )
        meta = {
            "build": {
                "skip": "True",
                "script": "python setup.py install",
                "number": 0,
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(expected_message.format("build", "ski"), lints)

        meta = {
            "build": {
                "ski": "True",
                "script": "python setup.py install",
                "number": 0,
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(expected_message.format("build", "ski"), lints)

        meta = {"source": {"urll": "http://test"}}
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(expected_message.format("source", "urll"), lints)

        meta = {"source": [{"urll": "http://test"}, {"url": "https://test"}]}
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(expected_message.format("source", "urll"), lints)

    def test_outputs(self):
        meta = OrderedDict([["outputs", [{"name": "asd"}]]])
        lints, hints = linter.lintify_recipe(meta)

    def test_version(self):
        meta = {"package": {"name": "python", "version": "3.6.4"}}
        expected_message = "Package version 3.6.4 doesn't match conda spec"
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(expected_message, lints)

        meta = {"package": {"name": "python", "version": "2.0.0~alpha0"}}
        expected_message = (
            "Package version 2.0.0~alpha0 doesn't match conda spec"
        )
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(expected_message, lints)

    def test_rattler_version(self):
        meta = {"package": {"name": "python", "version": "3.6.4"}}
        expected_message = "Package version 3.6.4 doesn't match conda spec"
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(expected_message, lints)

        meta = {"package": {"name": "python", "version": "2.0.0~alpha0"}}
        expected_message = (
            "Package version 2.0.0~alpha0 doesn't match conda spec"
        )
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(expected_message, lints)

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_examples(self):
        msg = (
            "Please move the recipe out of the example dir and into its "
            "own dir."
        )
        lints, hints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": ["support"]}},
            recipe_dir="recipes/example/",
            conda_forge=True,
        )
        self.assertIn(msg, lints)
        lints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": ["support"]}},
            recipe_dir="python",
            conda_forge=True,
        )
        self.assertNotIn(msg, lints)

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_rattler_examples(self):
        msg = (
            "Please move the recipe out of the example dir and into its "
            "own dir."
        )
        lints, hints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": ["support"]}},
            recipe_dir="recipes/example/",
            conda_forge=True,
        )
        self.assertIn(msg, lints)
        lints = linter.lintify_recipe(
            {"extra": {"recipe-maintainers": ["support"]}},
            recipe_dir="python",
            conda_forge=True,
        )
        self.assertNotIn(msg, lints)

    def test_multiple_sources(self):
        lints = linter.main(
            os.path.join(_thisdir, "recipes", "multiple_sources")
        )
        assert not lints

    def test_noarch_platforms(self):
        lints = linter.main(
            os.path.join(_thisdir, "recipes", "noarch_platforms", "recipe")
        )
        assert not lints

    def test_noarch_selector_variants(self):
        lints = linter.main(
            os.path.join(_thisdir, "recipes", "noarch_selector_variants")
        )
        assert not lints

    def test_string_source(self):
        url = "http://mistake.com/v1.0.tar.gz"
        lints, hints = linter.lintify_recipe({"source": url})
        msg = (
            'The "source" section was expected to be a dictionary or a '
            "list, but got a {}.{}."
        ).format(type(url).__module__, type(url).__name__)
        self.assertIn(msg, lints)

    def test_single_space_pins(self):
        meta = {
            "requirements": {
                "build": ["{{ compilers('c') }}", "python >=3", "pip   19"],
                "host": ["python >= 2", "libcblas 3.8.* *netlib"],
                "run": ["xonsh>1.0", "conda= 4.*", "conda-smithy<=54.*"],
            }
        }
        lints, hints = linter.lintify_recipe(meta)
        filtered_lints = [
            lint for lint in lints if lint.startswith("``requirements: ")
        ]
        expected_messages = [
            "``requirements: host: python >= 2`` should not contain a space between "
            "relational operator and the version, i.e. ``python >=2``",
            "``requirements: run: xonsh>1.0`` must contain a space between the "
            "name and the pin, i.e. ``xonsh >1.0``",
            "``requirements: run: conda= 4.*`` must contain a space between the "
            "name and the pin, i.e. ``conda =4.*``",
            "``requirements: run: conda-smithy<=54.*`` must contain a space "
            "between the name and the pin, i.e. ``conda-smithy <=54.*``",
        ]
        self.assertEqual(expected_messages, filtered_lints)

    def test_rattler_single_space_pins(self):
        meta = {
            "requirements": {
                "build": ["${{ compilers('c') }}", "python >=3", "pip   19"],
                "host": ["python >= 2", "libcblas 3.8.* *netlib"],
                "run": ["xonsh>1.0", "conda= 4.*", "conda-smithy<=54.*"],
            }
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        filtered_lints = [
            lint for lint in lints if lint.startswith("``requirements: ")
        ]
        expected_messages = [
            "``requirements: host: python >= 2`` should not contain a space between "
            "relational operator and the version, i.e. ``python >=2``",
            "``requirements: run: xonsh>1.0`` must contain a space between the "
            "name and the pin, i.e. ``xonsh >1.0``",
            "``requirements: run: conda= 4.*`` must contain a space between the "
            "name and the pin, i.e. ``conda =4.*``",
            "``requirements: run: conda-smithy<=54.*`` must contain a space "
            "between the name and the pin, i.e. ``conda-smithy <=54.*``",
        ]
        self.assertEqual(expected_messages, filtered_lints)

    def test_empty_host(self):
        meta = {"requirements": {"build": None, "host": None, "run": None}}
        # Test that this doesn't crash
        lints, hints = linter.lintify_recipe(meta)

    def test_rattler_empty_host(self):
        meta = {"requirements": {"build": None, "host": None, "run": None}}
        # Test that this doesn't crash
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)

    def test_python_requirements(self):
        meta = {"requirements": {"host": ["python >=3"]}}
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(
            "If python is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {
            "requirements": {"host": ["python >=3"]},
            "outputs": [{"name": "foo"}],
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(
            "If python is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {"requirements": {"host": ["python >=3", "python"]}}
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(
            "Non noarch packages should have python requirement without any version constraints.",
            lints,
        )

        meta = {"requirements": {"host": ["python >=3"]}}
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(
            "Non noarch packages should have python requirement without any version constraints.",
            lints,
        )

        meta = {
            "requirements": {"host": ["python"], "run": ["python-dateutil"]}
        }
        # Test that this doesn't crash
        lints, hints = linter.lintify_recipe(meta)

    def test_rattler_python_requirements(self):
        meta = {"requirements": {"host": ["python >=3"]}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(
            "If python is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {
            "requirements": {"host": ["python >=3"]},
            "outputs": [{"name": "foo"}],
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(
            "If python is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {"requirements": {"host": ["python >=3", "python"]}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(
            "Non noarch packages should have python requirement without any version constraints.",
            lints,
        )

        meta = {"requirements": {"host": ["python >=3"]}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(
            "Non noarch packages should have python requirement without any version constraints.",
            lints,
        )

        meta = {
            "requirements": {"host": ["python"], "run": ["python-dateutil"]}
        }
        # Test that this doesn't crash
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)

    def test_r_base_requirements(self):
        meta = {"requirements": {"host": ["r-base >=3.5"]}}
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(
            "If r-base is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {
            "requirements": {"host": ["r-base >=3.5"]},
            "outputs": [{"name": "foo"}],
        }
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(
            "If r-base is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {"requirements": {"host": ["r-base >=3.5", "r-base"]}}
        lints, hints = linter.lintify_recipe(meta)
        self.assertNotIn(
            "Non noarch packages should have r-base requirement without any version constraints.",
            lints,
        )

        meta = {"requirements": {"host": ["r-base >=3.5"]}}
        lints, hints = linter.lintify_recipe(meta)
        self.assertIn(
            "Non noarch packages should have r-base requirement without any version constraints.",
            lints,
        )

    def test_rattler_r_base_requirements(self):
        meta = {"requirements": {"host": ["r-base >=3.5"]}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(
            "If r-base is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {
            "requirements": {"host": ["r-base >=3.5"]},
            "outputs": [{"name": "foo"}],
        }
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(
            "If r-base is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {"requirements": {"host": ["r-base >=3.5", "r-base"]}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertNotIn(
            "Non noarch packages should have r-base requirement without any version constraints.",
            lints,
        )

        meta = {"requirements": {"host": ["r-base >=3.5"]}}
        lints, hints = linter.lintify_recipe(meta, is_rattler_build=True)
        self.assertIn(
            "Non noarch packages should have r-base requirement without any version constraints.",
            lints,
        )

    @pytest.mark.skipif(
        shutil.which("shellcheck") is None, reason="shellcheck not found"
    )
    def test_build_sh_with_shellcheck_findings(self):
        lints, hints = linter.main(
            os.path.join(_thisdir, "recipes", "build_script_with_findings"),
            return_hints=True,
        )
        assert any(
            "Whenever possible fix all shellcheck findings" in h for h in hints
        )
        assert len(hints) < 100

    @pytest.mark.skipif(
        shutil.which("shellcheck") is None, reason="shellcheck not found"
    )
    def test_rattler_build_sh_with_shellcheck_findings(self):
        recipe_dir = os.path.join(
            _thisdir,
            "recipes",
            "rattler_recipes",
            "build_script_with_findings",
        )

        lints, hints = linter.main(
            recipe_dir, return_hints=True, feedstock_dir=recipe_dir
        )

        assert any(
            "Whenever possible fix all shellcheck findings" in h for h in hints
        )
        assert len(hints) < 100

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_mpl_base_hint(self):
        meta = {
            "requirements": {
                "run": ["matplotlib >=2.3"],
            },
        }
        lints, hints = linter.lintify_recipe(meta, conda_forge=True)
        expected = "Recipes should usually depend on `matplotlib-base`"
        self.assertTrue(any(hint.startswith(expected) for hint in hints))

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_rattler_mpl_base_hint(self):
        meta = {
            "requirements": {
                "run": ["matplotlib >=2.3"],
            },
        }
        lints, hints = linter.lintify_recipe(
            meta, conda_forge=True, is_rattler_build=True
        )
        expected = "Recipes should usually depend on `matplotlib-base`"
        self.assertTrue(any(hint.startswith(expected) for hint in hints))

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_mpl_base_hint_outputs(self):
        meta = {
            "outputs": [
                {
                    "requirements": {
                        "run": ["matplotlib >=2.3"],
                    },
                },
            ],
        }
        lints, hints = linter.lintify_recipe(meta, conda_forge=True)
        expected = "Recipes should usually depend on `matplotlib-base`"
        self.assertTrue(any(hint.startswith(expected) for hint in hints))

    @unittest.skipUnless(is_gh_token_set(), "GH_TOKEN not set")
    def test_rattler_mpl_base_hint_outputs(self):
        meta = {
            "outputs": [
                {
                    "requirements": {
                        "run": ["matplotlib >=2.3"],
                    },
                },
            ],
        }
        lints, hints = linter.lintify_recipe(
            meta, conda_forge=True, is_rattler_build=True
        )
        expected = "Recipes should usually depend on `matplotlib-base`"
        self.assertTrue(any(hint.startswith(expected) for hint in hints))

    def test_rust_license_bundling(self):
        # Case where cargo-bundle-licenses is missing
        meta_missing_license = {
            "requirements": {"build": ["{{ compiler('rust') }}"]},
        }

        lints, hints = linter.lintify_recipe(meta_missing_license)
        expected_msg = (
            "Rust packages must include the licenses of the Rust dependencies. "
            "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust"
        )
        self.assertIn(expected_msg, lints)

        # Case where cargo-bundle-licenses is present
        meta_with_license = {
            "requirements": {
                "build": ["{{ compiler('rust') }}", "cargo-bundle-licenses"]
            },
        }

        lints, hints = linter.lintify_recipe(meta_with_license)
        self.assertNotIn(expected_msg, lints)

    def test_rattler_rust_license_bundling(self):
        # Case where cargo-bundle-licenses is missing
        meta_missing_license = {
            "requirements": {"build": ["${{ compiler('rust') }}"]},
        }

        lints, hints = linter.lintify_recipe(
            meta_missing_license, is_rattler_build=True
        )
        expected_msg = (
            "Rust packages must include the licenses of the Rust dependencies. "
            "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust"
        )
        self.assertIn(expected_msg, lints)

        # Case where cargo-bundle-licenses is present
        meta_with_license = {
            "requirements": {
                "build": ["${{ compiler('rust') }}", "cargo-bundle-licenses"]
            },
        }

        lints, hints = linter.lintify_recipe(
            meta_with_license, is_rattler_build=True
        )
        self.assertNotIn(expected_msg, lints)

    def test_go_license_bundling(self):
        # Case where go-licenses is missing
        meta_missing_license = {
            "requirements": {"build": ["{{ compiler('go') }}"]},
        }

        lints, hints = linter.lintify_recipe(meta_missing_license)
        expected_msg = (
            "Go packages must include the licenses of the Go dependencies. "
            "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go"
        )
        self.assertIn(expected_msg, lints)

        # Case where go-licenses is present
        meta_with_license = {
            "requirements": {"build": ["{{ compiler('go') }}", "go-licenses"]},
        }

        lints, hints = linter.lintify_recipe(meta_with_license)
        self.assertNotIn(expected_msg, lints)

    def test_rattler_go_license_bundling(self):
        # Case where go-licenses is missing
        meta_missing_license = {
            "requirements": {"build": ["${{ compiler('go') }}"]},
        }

        lints, hints = linter.lintify_recipe(
            meta_missing_license, is_rattler_build=True
        )
        expected_msg = (
            "Go packages must include the licenses of the Go dependencies. "
            "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go"
        )
        self.assertIn(expected_msg, lints)

        # Case where go-licenses is present
        meta_with_license = {
            "requirements": {
                "build": ["${{ compiler('go') }}", "go-licenses"]
            },
        }

        lints, hints = linter.lintify_recipe(
            meta_with_license, is_rattler_build=True
        )
        self.assertNotIn(expected_msg, lints)


@pytest.mark.cli
class TestCLI_recipe_lint(unittest.TestCase):
    def test_cli_fail(self):
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    textwrap.dedent(
                        """
                    package:
                        name: 'test_package'
                    build: []
                    requirements: []
                    """
                    )
                )
            child = subprocess.Popen(
                ["conda-smithy", "recipe-lint", recipe_dir],
                stdout=subprocess.PIPE,
            )
            out, _ = child.communicate()
            self.assertEqual(child.returncode, 1, out)

    def test_cli_success(self):
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    textwrap.dedent(
                        """
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
                    """
                    )
                )
            child = subprocess.Popen(
                ["conda-smithy", "recipe-lint", recipe_dir],
                stdout=subprocess.PIPE,
            )
            out, _ = child.communicate()
            self.assertEqual(child.returncode, 0, out)

    def test_cli_environ(self):
        with tmp_directory() as recipe_dir:
            with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    textwrap.dedent(
                        """
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
                    """
                    )
                )
            child = subprocess.Popen(
                ["conda-smithy", "recipe-lint", recipe_dir],
                stdout=subprocess.PIPE,
            )
            out, _ = child.communicate()
            self.assertEqual(child.returncode, 0, out)

    def test_unicode(self):
        """
        Tests that unicode does not confuse the linter.
        """
        with tmp_directory() as recipe_dir:
            with io.open(
                os.path.join(recipe_dir, "meta.yaml"), "wt", encoding="utf-8"
            ) as fh:
                fh.write(
                    """
                    package:
                        name: 'test_package'
                    build:
                        number: 0
                    about:
                        home: something
                        license: something else
                        summary: αβɣ
                        description: moɿɘ uniɔobɘ!
                         """
                )
            # Just run it and make sure it does not raise.
            linter.main(recipe_dir)

    def test_jinja_variable_def(self):
        expected_message = (
            "Jinja2 variable definitions are suggested to "
            "take a ``{{%<one space>set<one space>"
            "<variable name><one space>=<one space>"
            "<expression><one space>%}}`` form. See lines "
            "{}".format([2])
        )

        with tmp_directory() as recipe_dir:

            def assert_jinja(jinja_var, is_good=True):
                with io.open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(
                        """
                             {{% set name = "conda-smithy" %}}
                             {}
                             """.format(
                            jinja_var
                        )
                    )
                lints, hints = linter.lintify_recipe({}, recipe_dir)
                if is_good:
                    message = (
                        "Found lints when there shouldn't have been a "
                        "lint for '{}'.".format(jinja_var)
                    )
                else:
                    message = (
                        "Expecting lints for '{}', but didn't get any."
                        "".format(jinja_var)
                    )
                self.assertEqual(
                    not is_good,
                    any(lint.startswith(expected_message) for lint in lints),
                    message,
                )

            assert_jinja('{% set version = "0.27.3" %}')
            assert_jinja('{% set version="0.27.3" %}', is_good=False)
            assert_jinja('{%set version = "0.27.3" %}', is_good=False)
            assert_jinja('{% set version = "0.27.3"%}', is_good=False)
            assert_jinja('{% set version= "0.27.3"%}', is_good=False)


if __name__ == "__main__":
    unittest.main()
