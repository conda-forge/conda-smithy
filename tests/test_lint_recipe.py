#!/usr/bin/env python
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path

import pytest

import conda_smithy.lint_recipe as linter
from conda_smithy.linter import hints
from conda_smithy.linter.utils import (
    CONDA_BUILD_TOOL,
    RATTLER_BUILD_TOOL,
    VALID_PYTHON_BUILD_BACKENDS,
)
from conda_smithy.utils import get_yaml, render_meta_yaml

_thisdir = os.path.abspath(os.path.dirname(__file__))


@contextmanager
def get_recipe_in_dir(recipe_name: str) -> Path:
    base_dir = Path(__file__).parent
    recipe_path = base_dir / "recipes" / recipe_name
    assert recipe_path.exists(), f"Recipe {recipe_name} does not exist"

    # create a temporary directory to copy the recipe into
    with tmp_directory() as tmp_dir:
        # copy the file into the temporary directory
        recipe_folder = Path(tmp_dir) / "recipe"
        recipe_folder.mkdir()
        shutil.copy(recipe_path, recipe_folder / "recipe.yaml")

        try:
            yield recipe_folder
        finally:
            pass


@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp("recipe_")
    yield tmp_dir
    shutil.rmtree(tmp_dir)


@pytest.mark.parametrize(
    "comp_lang",
    [
        "c",
        "cxx",
        "fortran",
        "rust",
        "m2w64_c",
        "m2w64_cxx",
        "m2w64_fortran",
        "go-cgo",
        "go-nocgo",
    ],
)
def test_stdlib_lint(comp_lang):
    expected_message = "This recipe is using a compiler"

    with tmp_directory() as recipe_dir:
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
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
        if comp_lang == "go-nocgo":
            # This doesn't need a stdlib
            assert not any(lint.startswith(expected_message) for lint in lints)
        else:
            assert any(lint.startswith(expected_message) for lint in lints)


def test_m2w64_stdlib_legal():
    # allow recipes that _only_ depend on {{ stdlib("m2w64_c") }}
    avoid_message = "stdlib"

    with tmp_directory() as recipe_dir:
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                requirements:
                  build:
                    - {{ stdlib("m2w64_c") }}
                    - {{ compiler("m2w64_c") }}
                """
            )

        lints, _ = linter.main(recipe_dir, return_hints=True)
        assert not any(avoid_message in lint for lint in lints)


@pytest.mark.parametrize(
    "comp_lang",
    [
        "c",
        "cxx",
        "fortran",
        "rust",
        "m2w64_c",
        "m2w64_cxx",
        "m2w64_fortran",
        "go-cgo",
        "go-nocgo",
    ],
)
def test_v1_stdlib_hint(comp_lang):
    expected_message = "This recipe is using a compiler"

    with tmp_directory() as recipe_dir:
        Path(recipe_dir).joinpath("recipe.yaml").write_text(
            f"""
                package:
                   name: foo
                requirements:
                  build:
                    # since we're in an f-string: double up braces (2->4)
                    - ${{{{ compiler('{comp_lang}') }}}}
                """
        )
        Path(recipe_dir).joinpath("conda-forge.yml").write_text(
            "conda_build_tool: rattler-build"
        )

        lints, _ = linter.main(recipe_dir, feedstock_dir=recipe_dir, return_hints=True)
        if comp_lang == "go-nocgo":
            assert not any(lint.startswith(expected_message) for lint in lints)
        else:
            assert any(lint.startswith(expected_message) for lint in lints)


def test_sysroot_lint():
    expected_message = "You're setting a requirement on sysroot"

    with tmp_directory() as recipe_dir:
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
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


@pytest.mark.parametrize("where", ["run", "run_constrained"])
def test_osx_lint(where):
    expected_message = "You're setting a constraint on the `__osx` virtual"

    with tmp_directory() as recipe_dir:
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
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


def test_stdlib_lints_multi_output():
    with tmp_directory() as recipe_dir:
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
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
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
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


def test_recipe_v1_osx_noarch_hint():
    # don't warn on packages that are using __osx as a noarch-marker, see
    # https://conda-forge.org/docs/maintainer/knowledge_base/#noarch-packages-with-os-specific-dependencies
    avoid_message = "You're setting a constraint on the `__osx` virtual"

    with tmp_directory() as recipe_dir:
        with open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
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

        with open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
            fh.write("conda_build_tool: rattler-build")

        _, hints = linter.main(recipe_dir, return_hints=True, feedstock_dir=recipe_dir)
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
        with open(os.path.join(rdir, "conda_build_config.yaml")) as fh:
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


@pytest.mark.parametrize("recipe_version", [0, 1])
def test_license_file_required(recipe_version: int):
    meta = {
        "about": {
            "home": "a URL",
            "summary": "A test summary",
            "license": "MIT",
        }
    }
    lints, hints = linter.lintify_meta_yaml(meta, recipe_version=recipe_version)
    expected_message = "license_file entry is missing, but is required."
    assert expected_message in lints


@pytest.mark.parametrize("recipe_version", [0, 1])
def test_license_file_empty(recipe_version: int):
    meta = {
        "about": {
            "home": "a URL",
            "summary": "A test summary",
            "license": "LicenseRef-Something",
            "license_family": "LGPL",
            "license_file": None,
        }
    }
    lints, hints = linter.lintify_meta_yaml(meta, recipe_version=recipe_version)
    expected_message = "license_file entry is missing, but is required."
    assert expected_message in lints


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
def test_v1_cbc_osx_hints(
    std_selector, with_linux, reverse_arch, macdt, v_std, sdk, exp_lint
):
    with tmp_directory() as recipe_dir:
        recipe_dir = Path(recipe_dir)
        recipe_dir.joinpath("recipe.yaml").write_text("package:\n  name: foo")

        recipe_dir.joinpath("conda-forge.yml").write_text(
            "conda_build_tool: rattler-build"
        )

        with open(recipe_dir / "variants.yaml", "a") as fh:
            if macdt is not None:
                fh.write(
                    textwrap.dedent(
                        f"""\
                        MACOSX_DEPLOYMENT_TARGET:
                          - if: osx
                            then:
                              - {macdt[0]}
                              - {macdt[1]}
                    """
                    )
                )
            if v_std is not None or with_linux:
                arch1 = "arm64" if reverse_arch[1] else "x86_64"
                arch2 = "x86_64" if reverse_arch[1] else "arm64"

                fh.write(textwrap.dedent("c_stdlib_version:\n"))

                if v_std is not None:
                    fh.write(
                        textwrap.dedent(
                            f"""\
                            - if: {std_selector} and {arch1}
                              then: {v_std[0]}
                        """
                        )
                    )
                if v_std is not None and len(v_std) > 1:
                    fh.write(
                        textwrap.dedent(
                            f"""\
                            - if: {std_selector} and {arch2}
                              then: {v_std[1]}
                        """
                        )
                    )
                if with_linux:
                    fh.write(
                        textwrap.dedent(
                            """\
                            - if: linux
                              then: 2.17
                        """
                        )
                    )
            if sdk is not None:
                # often SDK is set uniformly for osx; test this as well
                if len(sdk) == 2:
                    fh.write(
                        textwrap.dedent(
                            f"""\
                            MACOSX_SDK_VERSION:
                              - if: osx and {"arm64" if reverse_arch[2] else "x86_64"}
                                then: {sdk[0]}
                              - if: osx and {"x86_64" if reverse_arch[2] else "arm64"}
                                then: {sdk[1]}
                        """
                        )
                    )
                else:
                    fh.write(
                        textwrap.dedent(
                            f"""\
                            MACOSX_SDK_VERSION:
                              - if: osx
                                then: {sdk[0]}
                        """
                        )
                    )
        # run the linter
        lints, _ = linter.main(recipe_dir, return_hints=True, feedstock_dir=recipe_dir)
        # show CBC/hints for debugging
        lines = recipe_dir.joinpath("variants.yaml").read_text().splitlines()
        print("".join(lines))
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


class TestLinter(unittest.TestCase):
    def test_bad_top_level(self):
        meta = OrderedDict([["package", {}], ["build", {}], ["sources", {}]])
        lints, hints = linter.lintify_meta_yaml(meta)
        expected_msg = "The top level meta key sources is unexpected"
        self.assertIn(expected_msg, lints)

    def test_recipe_v1_bad_top_level(self):
        meta = OrderedDict([["package", {}], ["build", {}], ["sources", {}]])
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        expected_msg = "The top level meta key sources is unexpected"
        self.assertIn(expected_msg, lints)

    def test_bad_order(self):
        meta = OrderedDict([["package", {}], ["build", {}], ["source", {}]])
        lints, hints = linter.lintify_meta_yaml(meta)
        expected_msg = (
            "The top level meta keys are in an unexpected "
            "order. Expecting ['package', 'source', 'build']."
        )
        self.assertIn(expected_msg, lints)

    def test_missing_about_license_and_summary(self):
        meta = {"about": {"home": "a URL"}}
        lints, hints = linter.lintify_meta_yaml(meta)
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
        lints, hints = linter.lintify_meta_yaml(meta)
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
        lints, hints = linter.lintify_meta_yaml(meta)
        expected = "about/license_family 'BSD3' not allowed"
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

    def test_missing_about_home(self):
        meta = {"about": {"license": "BSD", "summary": "A test summary"}}
        lints, hints = linter.lintify_meta_yaml(meta)
        expected_message = "The home item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_missing_about_homepage_empty(self):
        meta = {"about": {"homepage": "", "summary": "", "license": ""}}
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        expected_message = "The homepage item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The license item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The summary item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_missing_about_home_empty(self):
        meta = {"about": {"home": "", "summary": "", "license": ""}}
        lints, hints = linter.lintify_meta_yaml(meta)
        expected_message = "The home item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The license item is expected in the about section."
        self.assertIn(expected_message, lints)

        expected_message = "The summary item is expected in the about section."
        self.assertIn(expected_message, lints)

    def test_noarch_value(self):
        meta = {"build": {"noarch": "true"}}
        expected = "Invalid `noarch` value `true`. Should be one of"
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertTrue(any(lint.startswith(expected) for lint in lints))

    def test_maintainers_section(self):
        expected_message = (
            "The recipe could do with some maintainers listed "
            "in the `extra/recipe-maintainers` section."
        )

        lints, hints = linter.lintify_meta_yaml({"extra": {"recipe-maintainers": []}})
        self.assertIn(expected_message, lints)

        # No extra section at all.
        lints, hints = linter.lintify_meta_yaml({})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {"extra": {"recipe-maintainers": ["a"]}}
        )
        self.assertNotIn(expected_message, lints)

        expected_message = (
            'The "extra" section was expected to be a dictionary, but got a list.'
        )
        lints, hints = linter.lintify_meta_yaml({"extra": ["recipe-maintainers"]})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {"extra": {"recipe-maintainers": "Luke"}}
        )
        expected_message = "Recipe maintainers should be a json list."
        self.assertIn(expected_message, lints)

    def test_test_section(self):
        expected_message = "The recipe must have some tests."

        lints, hints = linter.lintify_meta_yaml({})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml({"test": {"files": "foo"}})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml({"test": {"imports": "sys"}})
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml({"outputs": [{"name": "foo"}]})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {"outputs": [{"name": "foo", "test": {"files": "foo"}}]}
        )
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {"outputs": [{"name": "foo", "test": {"imports": "sys"}}]}
        )
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
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

        lints, hints = linter.lintify_meta_yaml(
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

    def test_recipe_v1_test_section(self):
        expected_message = "The recipe must have some tests."

        lints, hints = linter.lintify_meta_yaml({}, recipe_version=1)
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {"tests": [{"script": "sys"}]}, recipe_version=1
        )
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {"outputs": [{"name": "foo"}]}, recipe_version=1
        )
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {
                "outputs": [
                    {
                        "name": "foo",
                        "tests": [{"python": {"imports": ["sys"]}}],
                    }
                ]
            },
            recipe_version=1,
        )
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {
                "outputs": [
                    {"name": "foo", "tests": {"script": "sys"}},
                    {
                        "name": "foobar",
                    },
                ]
            },
            recipe_version=1,
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
            lints, hints = linter.lintify_meta_yaml({}, recipe_dir)
            self.assertIn(expected_message, lints)

            with open(os.path.join(recipe_dir, "run_test.py"), "w") as fh:
                fh.write("# foo")
            lints, hints = linter.lintify_meta_yaml({}, recipe_dir)
            self.assertNotIn(expected_message, lints)

    def test_recipe_v1_test_section_with_recipe(self):
        expected_message = "The recipe must have some tests."

        with tmp_directory() as recipe_dir:
            lints, hints = linter.lintify_meta_yaml({}, recipe_dir, recipe_version=1)
            self.assertIn(expected_message, lints)

            # Note: v1 recipes have no implicit "run_test.py" support
            with open(os.path.join(recipe_dir, "run_test.py"), "w") as fh:
                fh.write("# foo")
            lints, hints = linter.lintify_meta_yaml({}, recipe_dir, recipe_version=1)
            self.assertIn(expected_message, lints)

    def test_jinja2_vars(self):
        expected_message = (
            "Jinja2 variable references are suggested to take a ``{{<one space>"
            "<variable name><one space>}}`` form. See lines %s." % ([6, 8, 10, 11, 12])
        )

        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
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

            _, hints = linter.lintify_meta_yaml({}, recipe_dir)
            self.assertTrue(any(h.startswith(expected_message) for h in hints))

    def test_recipe_v1_jinja2_vars(self):
        expected_message = (
            "Jinja2 variable references are suggested to take a ``${{<one space>"
            "<variable name><one space>}}`` form. See lines %s." % ([6, 8, 10, 11, 12])
        )

        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
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

            _, hints = linter.lintify_meta_yaml({}, recipe_dir, recipe_version=1)
            self.assertTrue(any(h.startswith(expected_message) for h in hints))

    def test_selectors(self):
        expected_message = (
            "Selectors are suggested to take a "
            "``<two spaces>#<one space>[<expression>]`` form."
            f" See lines {[3]}"
        )

        with tmp_directory() as recipe_dir:

            def assert_selector(selector, is_good=True):
                with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(
                        f"""
                            package:
                               name: foo_py2  # [py2k]
                               {selector}
                             """
                    )
                lints, hints = linter.lintify_meta_yaml({}, recipe_dir)
                if is_good:
                    message = (
                        "Found lints when there shouldn't have been a "
                        f"lint for '{selector}'."
                    )
                else:
                    message = f"Expecting lints for '{selector}', but didn't get any."
                self.assertEqual(
                    not is_good,
                    any(lint.startswith(expected_message) for lint in lints),
                    message,
                )

            assert_selector("name: foo_py3      # [py3k]")
            assert_selector("name: foo_py3  [py3k]", is_good=False)
            assert_selector("name: foo_py3  #[py3k]", is_good=False)
            assert_selector("name: foo_py3 # [py3k]", is_good=False)

    def test_python_selectors(self):
        with tmp_directory() as recipe_dir:

            def assert_python_selector(meta_string, is_good=False, kind="lint"):
                assert kind in ("lint", "hint")
                if kind == "hint":
                    expected_start = "Old-style Python selectors (py27, py34, py35, py36) are deprecated"
                else:
                    expected_start = "Old-style Python selectors (py27, py35, etc) are only available"
                with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(meta_string)
                lints, hints = linter.main(recipe_dir, return_hints=True)
                if is_good:
                    message = (
                        "Found lints or hints when there shouldn't have "
                        f"been for '{meta_string}'."
                    )
                else:
                    message = f"Expected lints or hints for '{meta_string}', but didn't get any."
                problems = lints if kind == "lint" else hints
                self.assertEqual(
                    not is_good,
                    any(problem.startswith(expected_start) for problem in problems),
                    message,
                )

            assert_python_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [py27]
                            """,
                kind="hint",
            )
            assert_python_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [py310]
                            """,
                kind="lint",
            )
            assert_python_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello" # [py38]
                            """,
                kind="lint",
            )
            assert_python_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"   #   [py36]
                            """,
                kind="hint",
            )
            assert_python_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [win or py37]
                            """,
                kind="lint",
            )
            assert_python_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [py37 or win]
                            """,
                kind="lint",
            )
            assert_python_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [unix or py37 or win]
                            """,
                kind="lint",
            )
            assert_python_selector(
                """
                            build:
                              noarch: python
                              script:
                                - echo "hello"  # [unix or py37 or py27]
                            """,
                kind="lint",
            )
            assert_python_selector(
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

            def assert_noarch_selector(
                meta_string, line_number=None, is_good=False, skip=False
            ):
                with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(meta_string)
                if skip:
                    with open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
                        fh.write(
                            """
linter:
  skip:
    - lint_noarch_selectors
"""
                        )
                lints = linter.main(recipe_dir)
                if skip:
                    os.remove(os.path.join(recipe_dir, "conda-forge.yml"))

                if is_good:
                    message = (
                        "Found lints when there shouldn't have "
                        f"been a lint for '{meta_string}'."
                    )
                else:
                    message = f"Expected lints for '{meta_string}', but didn't get any."
                self.assertEqual(
                    not is_good,
                    any(lint.startswith(expected_start) for lint in lints),
                    message,
                )
                self.assertEqual(
                    not is_good,
                    any(
                        lint.startswith(expected_start)
                        and f"or selector on line {line_number}" in lint
                        for lint in lints
                    ),
                )

            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              skip: true  # [py2k]
                            """,
                line_number=4,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: generic
                              skip: true  # [win]
                            """,
                line_number=4,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: generic
                              skip: true  # [win]
                            """,
                is_good=True,
                skip=True,
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
                            """,
                line_number=8,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                              requirements:
                                host:
                                  - python
                                  - enum34     # [py2k]
                            """,
                line_number=7,
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
                            """,
                line_number=6,
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
                            """,
                line_number=8,
            )

    def test_recipe_v1_noarch_selectors(self):
        expected_start = "`noarch` packages can't have"

        with tmp_directory() as recipe_dir:

            def assert_noarch_selector(
                meta_string,
                is_good=False,
                has_noarch=False,
                skip=False,
            ):
                with open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
                    fh.write(meta_string)

                with open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
                    fh.write("conda_build_tool: rattler-build\n")
                    if has_noarch:
                        fh.write(
                            """
noarch_platforms:
  - win_64
  - linux_64
"""
                        )
                    if skip:
                        fh.write(
                            """
linter:
  skip:
    - lint_noarch_selectors
"""
                        )

                lints = linter.main(recipe_dir, feedstock_dir=recipe_dir)
                os.remove(os.path.join(recipe_dir, "conda-forge.yml"))
                if is_good:
                    message = (
                        "Found lints when there shouldn't have "
                        f"been a lint for '{meta_string}'."
                    )
                else:
                    message = f"Expected lints for '{meta_string}', but didn't get any."
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
                              skip:
                                - win
                """,
                is_good=True,
                skip=True,
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
                                - if: unix
                                  then: echo "hello"
                                - if: win
                                  then: echo "hello"
                              requirements:
                                build:
                                  - python
                                  - if: win
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
                                  - if: win
                                    then:
                                      - enum34
                            """,
                is_good=True,
                has_noarch=True,
            )
            assert_noarch_selector(
                """
                            build:
                              noarch: python
                            requirements:
                              host:
                                - python
                                - if: win
                                  then:
                                    - enum34
                            """
            )

    def test_suggest_noarch(self):
        expected_start = "Whenever possible python packages should use noarch."

        with tmp_directory() as recipe_dir:

            def assert_noarch_hint(meta_string, is_good=False):
                with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(meta_string)
                lints, hints = linter.main(recipe_dir, return_hints=True)
                if is_good:
                    message = (
                        "Found hints when there shouldn't have "
                        f"been a lint for '{meta_string}'."
                    )
                else:
                    message = f"Expected hints for '{meta_string}', but didn't get any."
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

    def test_suggest_v1_noarch(self):
        expected_start = "Whenever possible python packages should use noarch."
        with tmp_directory() as recipe_dir:

            def assert_noarch_hint(meta_string, is_good=False):
                with open(os.path.join(recipe_dir, "recipe.yaml"), "w") as fh:
                    fh.write(meta_string)

                with open(os.path.join(recipe_dir, "conda-forge.yml"), "w") as fh:
                    fh.write("conda_build_tool: rattler-build")

                lints, hints = linter.main(
                    recipe_dir, return_hints=True, feedstock_dir=recipe_dir
                )
                if is_good:
                    message = (
                        "Found hints when there shouldn't have "
                        f"been a hint for '{meta_string}'."
                    )
                else:
                    message = f"Expected hints for '{meta_string}', but didn't get any."
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
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set version = os.environ.get('WIBBLE') %}
                        package:
                           name: foo
                           version: {{ version }}
                         """
                )
            linter.main(recipe_dir)

    def test_jinja_load_file_regex(self):
        # Test that we can use load_file_regex in a recipe. We don't care about
        # the results here.
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "sha256"), "w") as fh:
                fh.write(
                    """
                        d0e46ea5fca7d4c077245fe0b4195a828d9d4d69be8a0bd46233b2c12abd2098  iwftc_osx.zip
                        8ce4dc535b21484f65027be56263d8b0d9f58e57532614e1a8f6881f3b8fe260  iwftc_win.zip
                        """
                )
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
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
            linter.main(recipe_dir)

    def test_jinja_load_file_data(self):
        # Test that we can use load_file_data in a recipe. We don't care about
        # the results here and/or the actual file data because the recipe linter
        # renders conda-build functions to just function stubs to pass the linting.
        # TODO: add *args and **kwargs for functions used to parse the file.
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set data = load_file_data("IDONTNEED", from_recipe_dir=True, recipe_dir=".") %}
                        package:
                          name: foo
                          version: {{ version }}
                        """
                )
            linter.main(recipe_dir)

    def test_jinja_load_setup_py_data(self):
        # Test that we can use load_setup_py_data in a recipe. We don't care about
        # the results here and/or the actual file data because the recipe linter
        # renders conda-build functions to just function stubs to pass the linting.
        # TODO: add *args and **kwargs for functions used to parse the file.
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set data = load_setup_py_data("IDONTNEED", from_recipe_dir=True, recipe_dir=".") %}
                        package:
                          name: foo
                          version: {{ version }}
                        """
                )
            linter.main(recipe_dir)

    def test_jinja_load_str_data(self):
        # Test that we can use load_str_data in a recipe. We don't care about
        # the results here and/or the actual file data because the recipe linter
        # renders conda-build functions to just function stubs to pass the linting.
        # TODO: add *args and **kwargs for functions used to parse the data.
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        {% set data = load_str_data("IDONTNEED", "json") %}
                        package:
                          name: foo
                          version: {{ version }}
                        """
                )
            linter.main(recipe_dir)

    def test_jinja_os_sep(self):
        # Test that we can use os.sep in a recipe.
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        package:
                           name: foo_
                           version: 1.0
                        build:
                          script: {{ os.sep }}
                         """
                )
            linter.main(recipe_dir)

    def test_target_platform(self):
        # Test that we can use target_platform in a recipe. We don't care about
        # the results here.
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    """
                        package:
                           name: foo_{{ target_platform }}
                           version: 1.0
                         """
                )
            linter.main(recipe_dir)

    def test_missing_build_number(self):
        expected_message = "The recipe must have a `build/number` section."

        meta = {
            "build": {
                "skip": "True",
                "script": "python setup.py install",
                "number": 0,
            }
        }
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(expected_message, lints)

        meta = {"build": {"skip": "True", "script": "python setup.py install"}}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(expected_message, lints)

    def test_bad_requirements_order(self):
        expected_message = (
            "The `requirements/` sections should be defined in "
            "the following order: build, host, run; "
            "instead saw: run, build."
        )

        meta = {"requirements": OrderedDict([["run", ["a"]], ["build", ["a"]]])}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(expected_message, lints)

        meta = {
            "requirements": OrderedDict(
                [["run", ["a"]], ["invalid", ["a"]], ["build", ["a"]]]
            )
        }
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(expected_message, lints)

        meta = {"requirements": OrderedDict([["build", ["a"]], ["run", ["a"]]])}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(expected_message, lints)

    def test_noarch_python_bound(self):
        expected_message = (
            "noarch: python recipes are required to have a lower bound on the "
            "python version. Typically this means putting "
            "`python >={{ python_min }}` in the `run` section of your "
            "recipe. You may also want to check the upstream source for "
            "the package's Python compatibility."
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
        lints, hints = linter.lintify_meta_yaml(meta)
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
        lints, hints = linter.lintify_meta_yaml(meta)
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
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(expected_message, lints)

    def test_no_sha_with_dl(self):
        expected_message = (
            "When defining a source/url please add a sha256, "
            "sha1 or md5 checksum (sha256 preferably)."
        )
        lints, hints = linter.lintify_meta_yaml({"source": {"url": None}})
        self.assertIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml({"source": {"url": None, "sha1": None}})
        self.assertNotIn(expected_message, lints)

        lints, hints = linter.lintify_meta_yaml(
            {"source": {"url": None, "sha256": None}}
        )
        self.assertNotIn(expected_message, lints, hints)

        meta = {"source": {"url": None, "md5": None}}
        self.assertNotIn(expected_message, linter.lintify_meta_yaml(meta))

    def test_redundant_license(self):
        meta = {
            "about": {
                "home": "a URL",
                "summary": "A test summary",
                "license": "MIT License",
            }
        }
        lints, hints = linter.lintify_meta_yaml(meta)
        expected_message = 'The recipe `license` should not include the word "License".'
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
            lints, hints = linter.lintify_meta_yaml(meta)
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
            lints, hints = linter.lintify_meta_yaml(meta)
            if good:
                self.assertNotIn(msg, hints)
            else:
                self.assertIn(msg, hints)

    def test_recipe_name(self):
        meta = {"package": {"name": "mp++"}}
        lints, hints = linter.lintify_meta_yaml(meta)
        expected_message = (
            "Recipe name has invalid characters. only lowercase alpha, "
            "numeric, underscores, hyphens and dots allowed"
        )
        self.assertIn(expected_message, lints)

    def test_recipe_v1_recipe_name(self):
        meta = {"package": {"name": "mp++"}}
        lints, _ = linter.lintify_meta_yaml(meta, recipe_version=1)
        expected_message = (
            "Recipe name has invalid characters. only lowercase alpha, "
            "numeric, underscores, hyphens and dots allowed"
        )
        self.assertIn(expected_message, lints)

        meta_with_context = {
            "context": {"blah": "mp++"},
            "package": {"name": "${{ blah }}"},
        }  # noqa
        lints, _ = linter.lintify_meta_yaml(meta_with_context, recipe_version=1)
        self.assertIn(expected_message, lints)

        meta_with_context = {"recipe": {"name": "mp++"}, "outputs": []}  # noqa
        lints, _ = linter.lintify_meta_yaml(meta_with_context, recipe_version=1)
        self.assertIn(expected_message, lints)

        # variable may be defined e.g. in conda_build_config.yaml
        # https://github.com/conda-forge/conda-smithy/issues/2224
        meta = {"package": {"name": "${{ variant_name }}"}}
        lints, _ = linter.lintify_meta_yaml(meta, recipe_version=1)
        self.assertNotIn(expected_message, lints)

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
                with open(os.path.join(recipe_dir, "meta.yaml"), "w") as f:
                    f.write(content)
                lints, hints = linter.lintify_meta_yaml({}, recipe_dir=recipe_dir)
                if lines > 1:
                    expected_message = (
                        f"There are {lines - 1} too many lines.  "
                        "There should be one empty line "
                        "at the end of the "
                        "file."
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
            os.path.join(_thisdir, "recipes", "cb3_jinja2_functions", "recipe")
        )
        assert not lints

    def test_maintainer_exists(self):
        lints, _ = linter.lintify_meta_yaml(
            {"extra": {"recipe-maintainers": ["support"]}}, conda_forge=True
        )
        expected_message = 'Recipe maintainer "support" does not exist'
        self.assertIn(expected_message, lints)

        lints, _ = linter.lintify_meta_yaml(
            {"extra": {"recipe-maintainers": ["isuruf"]}}, conda_forge=True
        )
        expected_message = 'Recipe maintainer "isuruf" does not exist'
        self.assertNotIn(expected_message, lints)

        lints, _ = linter.lintify_meta_yaml(
            {"extra": {"recipe-maintainers": ["conda-forge"]}},
            conda_forge=True,
        )
        expected_message = 'Recipe maintainer "conda-forge" does not exist'
        self.assertIn(expected_message, lints)

    def test_maintainer_exists_no_token(self):
        gh_token = os.environ.get("GH_TOKEN", None)
        try:
            if "GH_TOKEN" in os.environ:
                del os.environ["GH_TOKEN"]

            lints, _ = linter.lintify_meta_yaml(
                {"extra": {"recipe-maintainers": ["support"]}},
                conda_forge=True,
            )
            expected_message = 'Recipe maintainer "support" does not exist'
            self.assertIn(expected_message, lints)

            lints, _ = linter.lintify_meta_yaml(
                {"extra": {"recipe-maintainers": ["isuruf"]}}, conda_forge=True
            )
            expected_message = 'Recipe maintainer "isuruf" does not exist'
            self.assertNotIn(expected_message, lints)

            lints, _ = linter.lintify_meta_yaml(
                {"extra": {"recipe-maintainers": ["conda-forge"]}},
                conda_forge=True,
            )
            expected_message = 'Recipe maintainer "conda-forge" does not exist'
            self.assertIn(expected_message, lints)
        finally:
            if gh_token is not None:
                os.environ["GH_TOKEN"] = gh_token

    def test_maintainer_team_exists(self):
        lints, _ = linter.lintify_meta_yaml(
            {"extra": {"recipe-maintainers": ["conda-forge/blahblahblah-foobarblah"]}},
            conda_forge=True,
        )
        expected_message = 'Recipe maintainer team "conda-forge/blahblahblah-foobarblah" does not exist'
        self.assertIn(expected_message, lints)

        lints, _ = linter.lintify_meta_yaml(
            {"extra": {"recipe-maintainers": ["conda-forge/core"]}},
            conda_forge=True,
        )
        expected_message = 'Recipe maintainer team "conda-forge/Core" does not exist'
        self.assertNotIn(expected_message, lints)

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
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(expected_message.format("build", "ski"), lints)

        meta = {
            "build": {
                "ski": "True",
                "script": "python setup.py install",
                "number": 0,
            }
        }
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(expected_message.format("build", "ski"), lints)

        meta = {"source": {"urll": "http://test"}}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(expected_message.format("source", "urll"), lints)

        meta = {"source": [{"urll": "http://test"}, {"url": "https://test"}]}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(expected_message.format("source", "urll"), lints)

    def test_outputs(self):
        meta = OrderedDict([["outputs", [{"name": "asd"}]]])
        lints, hints = linter.lintify_meta_yaml(meta)

    def test_version(self):
        meta = {"package": {"name": "python", "version": "3.6.4"}}
        expected_message = "Package version 3.6.4 doesn't match conda spec"
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(expected_message, lints)

        meta = {"package": {"name": "python", "version": "2.0.0~alpha0"}}
        expected_message = "Package version 2.0.0~alpha0 doesn't match conda spec"
        lints, hints = linter.lintify_meta_yaml(meta)
        assert any(lint.startswith(expected_message) for lint in lints)

    def test_recipe_v1_version(self):
        meta = {"package": {"name": "python", "version": "3.6.4"}}
        expected_message = "Package version 3.6.4 doesn't match conda spec"
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        self.assertNotIn(expected_message, lints)

        meta = {"package": {"name": "python", "version": "2.0.0~alpha0"}}
        expected_message = "Package version 2.0.0~alpha0 doesn't match conda spec"
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        assert any(lint.startswith(expected_message) for lint in lints)

        # when having multiple outputs it should use recipe keyword
        meta = {"recipe": {"version": "2.0.0~alpha0"}, "outputs": []}
        expected_message = "Package version 2.0.0~alpha0 doesn't match conda spec"
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        assert any(lint.startswith(expected_message) for lint in lints)

        meta = {"package": {"name": "python"}}
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        expected_message = "Package version is missing."
        assert any(lint.startswith(expected_message) for lint in lints)

        # should handle integer versions
        meta = {"package": {"name": "python", "version": 2}}
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        expected_message = "Package version 2 doesn't match conda spec"
        self.assertNotIn(expected_message, lints)

    def test_recipe_v1_version_with_context(self):
        meta = {
            "context": {"foo": "3.6.4"},
            "package": {"name": "python", "version": "${{ foo }}"},
        }
        expected_message = "Package version 3.6.4 doesn't match conda spec"
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        self.assertNotIn(expected_message, lints)

        meta = {
            "context": {"bar": "2.0.0~alpha0"},
            "package": {"name": "python", "version": "${{ bar }}"},
        }
        expected_message = "Package version 2.0.0~alpha0 doesn't match conda spec"
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        assert any(lint.startswith(expected_message) for lint in lints)

        meta = {
            "context": {"foo": 2},
            "package": {"name": "python", "version": "${{ foo }}"},
        }
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        expected_message = "Package version 2 doesn't match conda spec"
        self.assertNotIn(expected_message, lints)

    def test_multiple_sources(self):
        lints = linter.main(os.path.join(_thisdir, "recipes", "multiple_sources"))
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
        lints, hints = linter.lintify_meta_yaml({"source": url})
        msg = (
            'The "source" section was expected to be a dictionary or a '
            f"list, but got a {type(url).__module__}.{type(url).__name__}."
        )
        self.assertIn(msg, lints)

    def test_single_space_pins(self):
        meta = {
            "requirements": {
                "build": ["{{ compilers('c') }}", "python >=3", "pip   19"],
                "host": ["python >= 2", "libcblas 3.8.* *netlib"],
                "run": ["xonsh>1.0", "conda= 4.*", "conda-smithy<=54.*"],
            }
        }
        lints, hints = linter.lintify_meta_yaml(meta)
        filtered_lints = [lint for lint in lints if lint.startswith("``requirements: ")]
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

    def test_recipe_v1_single_space_pins(self):
        meta = {
            "requirements": {
                "build": ["${{ compiler('c') }}", "python >=3", "pip   19"],
                "host": ["python >= 2", "libcblas 3.8.* *netlib"],
                "run": ["xonsh>1.0", "conda= 4.*", "conda-smithy<=54.*"],
            }
        }
        lints, hints = linter.lintify_meta_yaml(meta, recipe_version=1)
        filtered_lints = [lint for lint in lints if lint.startswith("``requirements: ")]
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
        lints, hints = linter.lintify_meta_yaml(meta)

    def test_python_requirements(self):
        meta = {"requirements": {"host": ["python >=3"]}}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(
            "If python is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {
            "requirements": {"host": ["python >=3"]},
            "outputs": [{"name": "foo"}],
        }
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(
            "If python is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {"requirements": {"host": ["python >=3", "python"]}}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(
            "Non noarch packages should have python requirement without any version constraints.",
            lints,
        )

        meta = {"requirements": {"host": ["python >=3"]}}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(
            "Non noarch packages should have python requirement without any version constraints.",
            lints,
        )

        meta = {"requirements": {"host": ["python"], "run": ["python-dateutil"]}}
        # Test that this doesn't crash
        lints, hints = linter.lintify_meta_yaml(meta)

    def test_r_base_requirements(self):
        meta = {"requirements": {"host": ["r-base >=3.5"]}}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertIn(
            "If r-base is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {
            "requirements": {"host": ["r-base >=3.5"]},
            "outputs": [{"name": "foo"}],
        }
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(
            "If r-base is a host requirement, it should be a run requirement.",
            lints,
        )

        meta = {"requirements": {"host": ["r-base >=3.5", "r-base"]}}
        lints, hints = linter.lintify_meta_yaml(meta)
        self.assertNotIn(
            "Non noarch packages should have r-base requirement without any version constraints.",
            lints,
        )

        meta = {"requirements": {"host": ["r-base >=3.5"]}}
        lints, hints = linter.lintify_meta_yaml(meta)
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
        assert any("Whenever possible fix all shellcheck findings" in h for h in hints)
        assert len(hints) < 100

    def test_mpl_base_hint(self):
        meta = {
            "requirements": {
                "run": ["matplotlib >=2.3"],
            },
        }
        lints, hints = linter.lintify_meta_yaml(meta, conda_forge=True)
        expected = "Recipes should usually depend on `matplotlib-base`"
        self.assertTrue(any(hint.startswith(expected) for hint in hints))

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
        lints, hints = linter.lintify_meta_yaml(meta, conda_forge=True)
        expected = "Recipes should usually depend on `matplotlib-base`"
        self.assertTrue(any(hint.startswith(expected) for hint in hints))


@pytest.mark.parametrize("recipe_version", [0, 1])
def test_rust_license_bundling(recipe_version: int):
    # Case where go-licenses is missing
    compiler = (
        "${{ compiler('rust') }}" if recipe_version == 1 else "{{ compiler('rust') }}"
    )
    meta_missing_license = {
        "requirements": {"build": [compiler]},
    }

    lints, hints = linter.lintify_meta_yaml(
        meta_missing_license, recipe_version=recipe_version
    )
    expected_msg = (
        "Rust packages must include the licenses of the Rust dependencies. "
        "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust"
    )
    assert expected_msg in lints

    # Case where cargo-bundle-licenses is present
    meta_with_license = {
        "requirements": {"build": [compiler, "cargo-bundle-licenses"]},
    }

    lints, hints = linter.lintify_meta_yaml(
        meta_with_license, recipe_version=recipe_version
    )
    assert expected_msg not in lints

    # cargo-bundle-licenses itself should not be linted
    meta_cargo_bundle_licenses = {
        "requirements": {"build": [compiler]},
        "package": {"name": "cargo-bundle-licenses"},
    }
    lints, hints = linter.lintify_meta_yaml(
        meta_cargo_bundle_licenses, recipe_version=recipe_version
    )
    assert expected_msg not in lints


@pytest.mark.parametrize("recipe_version", [0, 1])
def test_go_license_bundling(recipe_version: int):
    # Case where go-licenses is missing
    compiler = (
        "${{ compiler('go') }}" if recipe_version == 1 else "{{ compiler('go') }}"
    )
    meta_missing_license = {
        "requirements": {"build": [compiler]},
    }

    lints, hints = linter.lintify_meta_yaml(
        meta_missing_license, recipe_version=recipe_version
    )
    expected_msg = (
        "Go packages must include the licenses of the Go dependencies. "
        "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go"
    )
    assert expected_msg in lints

    # Case where go-licenses is present
    meta_with_license = {
        "requirements": {"build": [compiler, "go-licenses"]},
    }

    lints, hints = linter.lintify_meta_yaml(
        meta_with_license, recipe_version=recipe_version
    )
    assert expected_msg not in lints


@pytest.mark.cli
class TestCliRecipeLint(unittest.TestCase):
    def test_cli_fail(self):
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
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
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    textwrap.dedent(
                        """
                    package:
                        name: 'test_package'
                        version: 1.0.0
                    build:
                        number: 0
                    test:
                        imports:
                            - foo
                    about:
                        home: something
                        license: MIT
                        license_file: LICENSE
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
            with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                fh.write(
                    textwrap.dedent(
                        """
                    package:
                        name: 'test_package'
                        version: 1.0.0
                    build:
                        number: 0
                    test:
                        requires:
                            - python {{ environ['PY_VER'] + '*' }}  # [win]
                        imports:
                            - foo
                    about:
                        home: something
                        license: MIT
                        license_file: LICENSE
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
            with open(
                os.path.join(recipe_dir, "meta.yaml"), "w", encoding="utf-8"
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
            "take a ``{%<one space>set<one space>"
            "<variable name><one space>=<one space>"
            "<expression><one space>%}`` form. See lines "
            f"{[2]}"
        )

        with tmp_directory() as recipe_dir:

            def assert_jinja(jinja_var, is_good=True):
                with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
                    fh.write(
                        f"""
                             {{% set name = "conda-smithy" %}}
                             {jinja_var}
                             """
                    )
                lints, hints = linter.lintify_meta_yaml({}, recipe_dir)
                if is_good:
                    message = (
                        "Found lints when there shouldn't have been a "
                        f"lint for '{jinja_var}'."
                    )
                else:
                    message = f"Expecting lints for '{jinja_var}', but didn't get any."
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


def test_lint_no_builds():
    expected_message = "The feedstock has no `.ci_support` files and "

    with tmp_directory() as feedstock_dir:
        ci_support_dir = os.path.join(feedstock_dir, ".ci_support")
        os.makedirs(ci_support_dir, exist_ok=True)
        with open(os.path.join(ci_support_dir, "README"), "w") as fh:
            fh.write("blah")
        recipe_dir = os.path.join(feedstock_dir, "recipe")
        os.makedirs(recipe_dir, exist_ok=True)
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                """
            )

        lints = linter.main(recipe_dir, conda_forge=True)
        assert any(lint.startswith(expected_message) for lint in lints)

        with open(os.path.join(ci_support_dir, "blah.yaml"), "w") as fh:
            fh.write("blah")

        lints = linter.main(recipe_dir, conda_forge=True)
        assert not any(lint.startswith(expected_message) for lint in lints)


def test_lint_duplicate_cfyml():
    expected_message = (
        "The ``conda-forge.yml`` file is not allowed to have duplicate keys."
    )

    with tmp_directory() as feedstock_dir:
        cfyml = os.path.join(feedstock_dir, "conda-forge.yml")
        recipe_dir = os.path.join(feedstock_dir, "recipe")
        os.makedirs(recipe_dir, exist_ok=True)
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                """
                package:
                   name: foo
                """
            )

        with open(cfyml, "w") as fh:
            fh.write(
                textwrap.dedent(
                    """
                    blah: 1
                    blah: 2
                    """
                )
            )

        lints = linter.main(recipe_dir, conda_forge=True)
        assert any(lint.startswith(expected_message) for lint in lints)

        with open(cfyml, "w") as fh:
            fh.write(
                textwrap.dedent(
                    """
                    blah: 1
                    """
                )
            )

        lints = linter.main(recipe_dir, conda_forge=True)
        assert not any(lint.startswith(expected_message) for lint in lints)


def test_cfyml_wrong_os_version():
    expected_message = (
        "{'linux_64': 'wrong'} is not valid under any of the given schemas"
    )

    with tmp_directory() as feedstock_dir:
        cfyml = os.path.join(feedstock_dir, "conda-forge.yml")
        recipe_dir = os.path.join(feedstock_dir, "recipe")
        os.makedirs(recipe_dir, exist_ok=True)
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                """
                package:
                  name: foo
                """
            )

        with open(cfyml, "w") as fh:
            fh.write(
                textwrap.dedent(
                    """
                    os_version:
                      linux_64: wrong
                    """
                )
            )

        lints = linter.main(recipe_dir, conda_forge=True)
        assert any(expected_message in lint for lint in lints)


@pytest.mark.parametrize(
    "yaml_block,expected_message",
    [
        pytest.param(
            """
            {% set name = "libconeangle" %}
            {% set version = "0.1.1" %}

            package:
              name: {{ name|lower }}
              version: {{ version }}

            source:
              url: https://pypi.io/packages/source/{{ name[0] }}/{{ name }}/libconeangle-{{ version }}.tar.gz  # [unix]
              sha256: bc828be92fdf2d2d353b5e8bb95644068220d92809276312ff2d7bca0aa8b2d1  # [unix]
              url: https://pypi.org/packages/cp{{ CONDA_PY }}/{{ name[0] }}/{{ name }}/{{ name }}-{{ version }}-cp{{ CONDA_PY }}-cp{{ CONDA_PY }}-win_amd64.whl  # [win]
              sha256: 467a444ca9a46675b12d43b00462052dc00a16bc322944df8053b1573a492dce  # [win and py==38]
              sha256: b35c0643c9f1dd1c933c0a6d91b7368c32a3255e76594dea27d918b71c1166ed  # [win and py==39]
              sha256: a32e28b3e321bdb802f28a5f04d1df65071ab42eef06a6dc15ed656780c0361e  # [win and py==310]
            build:
              skip: true  # [py<38 or python_impl == 'pypy' or (win and py==311)]
              script: {{ PYTHON }} -m pip install . -vv  # [unix]
              script_env:  # [osx and arm64]
                - SKBUILD_CONFIGURE_OPTIONS=-DWITH_CBOOL_EXITCODE=0 -DWITH_CBOOL_EXITCODE__TRYRUN_OUTPUT='' -Df03real128_EXITCODE=1 -Df03real128_EXITCODE__TRYRUN_OUTPUT='' -Df18errorstop_EXITCODE=1 -Df18errorstop_EXITCODE__TRYRUN_OUTPUT=''  # [osx and arm64]
              script: {{ PYTHON }} -m pip install {{ name }}-{{ version }}-cp{{ CONDA_PY }}-cp{{ CONDA_PY }}-win_amd64.whl -vv  # [win]
              number: 3
            """,
            "PyPI default URL is now pypi.org",
            id="pypi.io",
        )
    ],
)
def test_hint_recipe(tmp_path, yaml_block: str, expected_message: str):
    (tmp_path / "meta.yaml").write_text(yaml_block)

    _, hints = linter.main(tmp_path, conda_forge=False, return_hints=True)
    assert any(list(expected_message in hint for hint in hints))


@pytest.mark.parametrize(
    "yaml_block,annotation",
    [
        pytest.param(
            """
            {% set name = "libconeangle" %}
            {% set version = "0.1.1" %}

            package:
              name: {{ name|lower }}
              version: {{ version }}

            source:
              url: https://pypi.org/packages/source/{{ name[0] }}/{{ name }}/libconeangle-{{ version }}.tar.gz  # [unix]
              sha256: bc828be92fdf2d2d353b5e8bb95644068220d92809276312ff2d7bca0aa8b2d1  # [unix]
              url: https://pypi.org/packages/cp{{ CONDA_PY }}/{{ name[0] }}/{{ name }}/{{ name }}-{{ version }}-cp{{ CONDA_PY }}-cp{{ CONDA_PY }}-win_amd64.whl  # [win]
              sha256: 467a444ca9a46675b12d43b00462052dc00a16bc322944df8053b1573a492dce  # [win and py==38]
              sha256: b35c0643c9f1dd1c933c0a6d91b7368c32a3255e76594dea27d918b71c1166ed  # [win and py==39]
              sha256: a32e28b3e321bdb802f28a5f04d1df65071ab42eef06a6dc15ed656780c0361e  # [win and py==310]
            build:
              skip: true  # [py<38 or python_impl == 'pypy' or (win and py==311)]
              script: {{ PYTHON }} -m pip install . -vv  # [unix]
              script_env:  # [osx and arm64]
                - SKBUILD_CONFIGURE_OPTIONS=-DWITH_CBOOL_EXITCODE=0 -DWITH_CBOOL_EXITCODE__TRYRUN_OUTPUT='' -Df03real128_EXITCODE=1 -Df03real128_EXITCODE__TRYRUN_OUTPUT='' -Df18errorstop_EXITCODE=1 -Df18errorstop_EXITCODE__TRYRUN_OUTPUT=''  # [osx and arm64]
              script: {{ PYTHON }} -m pip install {{ name }}-{{ version }}-cp{{ CONDA_PY }}-cp{{ CONDA_PY }}-win_amd64.whl -vv  # [win]
              number: 3
            """,
            "lint",
            id="libconeangle",
        ),
        pytest.param(
            """
            {% set name = "junit-xml" %}
            {% set version = "1.9" %}
            {% set python_tag = 'py2.py3' %}
            {% set use_wheel = True %}

            package:
              name: {{ name|lower }}
              version: {{ version }}

            source:
            {% if use_wheel %}
            - url: https://pypi.org/packages/{{ python_tag }}/{{ name[0] }}/{{ name }}/{{ name | replace('-', '_') }}-{{ version }}-{{ python_tag }}-none-any.whl
              sha256: "ec5ca1a55aefdd76d28fcc0b135251d156c7106fa979686a4b48d62b761b4732"
            {% else %}
            - url: https://pypi.org/packages/source/{{ name[0] }}/{{ name }}/{{ name }}-{{ version }}.tar.gz
              sha256: ""
            {% endif %}

            build:
              noarch: python
              number: 0
              {% if use_wheel %}
              script: "{{ PYTHON }} -m pip install --no-deps --ignore-installed --no-cache-dir -vvv *.whl"
              {% else %}
              script: "{{ PYTHON }} -m pip install --no-deps --ignore-installed --no-cache-dir -vvv ."
              {% endif %}
            """,
            "hint",
            id="junit-xml",
        ),
        pytest.param(
            """
            {% set name = "WeasyPrint" %}
            {% set version = "62.1" %}

            package:
              name: {{ name|lower }}
              version: {{ version }}

            source:
              url: https://files.pythonhosted.org/packages/py3/{{ (name|lower)[0] }}/{{ name|lower }}/{{ name|lower }}-{{ version }}-py3-none-any.whl
              sha256: 654d4c266336cbf9acc4da118c7778ef5839717e6055d5b8f995cf50be200c46

            build:
              number: 0
              noarch: python
              entry_points:
                - weasyprint = weasyprint.__main__:main
              script: {{ PYTHON }} -m pip install {{ name|lower }}-{{ version }}-py3-none-any.whl -vv
            """,
            "hint",
            id="weasyprint",
        ),
    ],
)
def test_lint_wheels(tmp_path, yaml_block, annotation):
    (tmp_path / "meta.yaml").write_text(yaml_block)
    expected_message = "wheel(s) in source"

    lints, hints = linter.main(tmp_path, conda_forge=False, return_hints=True)
    if annotation == "lint":
        assert any(expected_message in lint for lint in lints)
    else:
        assert any(expected_message in hint for hint in hints)


@pytest.mark.parametrize("recipe_version", [0, 1])
def test_pin_compatible_in_run_exports(recipe_version: int):
    meta = {
        "package": {
            "name": "apackage",
        }
    }

    if recipe_version == 1:
        meta["requirements"] = {
            "run_exports": ['${{ pin_compatible("apackage") }}'],
        }
    else:
        meta["build"] = {
            "run_exports": ["compatible_pin apackage"],
        }

    lints, hints = linter.lintify_meta_yaml(meta, recipe_version=recipe_version)
    expected = "pin_subpackage should be used instead"
    assert any(lint.startswith(expected) for lint in lints)


@pytest.mark.parametrize("recipe_version", [0, 1])
def test_pin_compatible_in_run_exports_output(recipe_version: int):
    if recipe_version == 1:
        meta = {
            "recipe": {
                "name": "apackage",
            },
            "outputs": [
                {
                    "package": {"name": "anoutput", "version": "0.1.0"},
                    "requirements": {
                        "run_exports": ['${{ pin_subpackage("notanoutput") }}'],
                    },
                }
            ],
        }
    else:
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

    lints, hints = linter.lintify_meta_yaml(meta, recipe_version=recipe_version)
    expected = "pin_compatible should be used instead"
    assert any(lint.startswith(expected) for lint in lints)


def test_v1_recipes():
    with get_recipe_in_dir("v1_recipes/recipe-no-lint.yaml") as recipe_dir:
        lints, hints = linter.main(str(recipe_dir), return_hints=True)
        assert not lints

    with get_recipe_in_dir("v1_recipes/torchaudio.yaml") as recipe_dir:
        lints, hints = linter.main(str(recipe_dir), return_hints=True)
        assert not lints

    with get_recipe_in_dir("v1_recipes/torchvision.yaml") as recipe_dir:
        lints, hints = linter.main(str(recipe_dir), return_hints=True)
        assert not lints

    with get_recipe_in_dir("v1_recipes/ada-url.yaml") as recipe_dir:
        lints, hints = linter.main(str(recipe_dir), return_hints=True)
        assert not lints


def test_v1_recipes_conda_forge():
    with get_recipe_in_dir("v1_recipes/recipe-fenics-dolfinx.yaml") as recipe_dir:
        lints, hints = linter.main(str(recipe_dir), return_hints=True, conda_forge=True)
        assert lints == [
            "The feedstock has no `.ci_support` files and thus will not build any packages."
        ]


def test_v1_recipes_ignore_run_exports():
    with get_recipe_in_dir(
        "v1_recipes/recipe-ignore_run_exports-no-lint.yaml"
    ) as recipe_dir:
        lints, hints = linter.main(str(recipe_dir), return_hints=True)
        assert not lints


def test_v1_no_test():
    with get_recipe_in_dir("v1_recipes/recipe-no-tests.yaml") as recipe_dir:
        lints, hints = linter.main(str(recipe_dir), return_hints=True)
        assert "The recipe must have some tests." in lints


def test_v1_package_name_version():
    with get_recipe_in_dir("v1_recipes/recipe-lint-name-version.yaml") as recipe_dir:
        lints, hints = linter.main(str(recipe_dir), return_hints=True)
        lint_1 = "Recipe name has invalid characters. only lowercase alpha, numeric, underscores, hyphens and dots allowed"
        lint_2 = "Package version $!@# doesn't match conda spec: Invalid version '$!@#': invalid character(s)"
        assert lint_1 in lints
        assert lint_2 in lints


@pytest.mark.parametrize("remove_top_level", [True, False])
@pytest.mark.parametrize(
    "outputs_to_add, outputs_expected_hints",
    [
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    run:
                      - python
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    - python
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    host:
                      - pip
                    run:
                      - python
                """
            ),
            [
                "No valid build backend found for Python recipe for package `python-output`"
            ],
        ),
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    build:
                      - pip
                    run:
                      - python
                - name: python-output2
                  requirements:
                    run:
                      - python
                """
            ),
            [
                "No valid build backend found for Python recipe for package `python-output`"
            ],
        ),
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    build:
                      - blah
                    host:
                      - pip
                    run:
                      - python
                """
            ),
            [
                "No valid build backend found for Python recipe for package `python-output`"
            ],
        ),
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    host:
                      - pip
                      - @@backend@@
                    run:
                      - python
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    build:
                      - pip
                      - @@backend@@
                    run:
                      - python
                - name: python-output2
                  requirements:
                    host:
                      - pip
                    run:
                      - python
                """
            ),
            [
                "No valid build backend found for Python recipe for package `python-output2`"
            ],
        ),
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    build:
                      - pip
                    run:
                      - python
                - name: python-output2
                  requirements:
                    host:
                      - pip
                    run:
                      - python
                """
            ),
            [
                "No valid build backend found for Python recipe for package `python-output2`",
                "No valid build backend found for Python recipe for package `python-output`",
            ],
        ),
        (
            textwrap.dedent(
                """
                - name: python-output
                  requirements:
                    build:
                      - pip
                      - setuptools
                    run:
                      - python
                - name: python-output2
                  requirements:
                    host:
                      - pip
                      - @@backend@@
                    run:
                      - python
                """
            ),
            [],
        ),
    ],
)
@pytest.mark.parametrize("backend", VALID_PYTHON_BUILD_BACKENDS)
@pytest.mark.parametrize(
    "meta_str,expected_hints",
    [
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  run:
                    - python
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  host:
                    - pip
                  run:
                    - python
                """
            ),
            ["No valid build backend found for Python recipe for package `python`"],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  build:
                    - blah
                  host:
                    - pip
                  run:
                    - python
                """
            ),
            ["No valid build backend found for Python recipe for package `python`"],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  host:
                    - pip
                    - @@backend@@
                  run:
                    - python
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  build:
                    - blah
                  host:
                    - pip
                    - @@backend@@
                  run:
                    - python
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  build:
                    - pip
                  run:
                    - python
                """
            ),
            ["No valid build backend found for Python recipe for package `python`"],
        ),
    ],
)
@pytest.mark.parametrize("skip", [False, True])
def test_hint_pip_no_build_backend(
    meta_str,
    expected_hints,
    backend,
    outputs_to_add,
    outputs_expected_hints,
    remove_top_level,
    skip,
    tmp_path,
):
    if skip:
        with open(tmp_path / "conda-forge.yml", "w") as fh:
            fh.write(
                """
linter:
  skip:
    - hint_pip_no_build_backend
"""
            )

    meta = get_yaml().load(meta_str.replace("@@backend@@", backend))
    if remove_top_level:
        meta.pop("requirements", None)
        # we expect no hints in this case
        _expected_hints = []
    else:
        _expected_hints = expected_hints

    if outputs_to_add:
        meta["outputs"] = get_yaml().load(
            outputs_to_add.replace("@@backend@@", backend)
        )

    if skip:
        total_expected_hints = []
    else:
        total_expected_hints = _expected_hints + outputs_expected_hints

    lints = []
    hints = []
    linter.run_conda_forge_specific(
        meta,
        str(tmp_path),
        lints,
        hints,
        recipe_version=0,
    )

    # make sure we have the expected hints
    for expected_hint in total_expected_hints:
        assert any(hint.startswith(expected_hint) for hint in hints), hints

    # in this case we should not hint at all
    if not total_expected_hints:
        assert all(
            "No valid build backend found for Python recipe for package" not in hint
            for hint in hints
        ), hints

    # it is not a lint
    assert all(
        "No valid build backend found for Python recipe for package" not in lint
        for lint in lints
    ), lints


@pytest.mark.parametrize(
    "meta_str,expected_hints",
    [
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  run:
                    - python
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  run:
                    - python
                """
            ),
            [
                "python {{ python_min }}",
                "python >={{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python
                """
            ),
            [
                "python {{ python_min }}",
                "python >={{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                test:
                  requires:
                    - python
                """
            ),
            [
                "python {{ python_min }}",
                "python >={{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  run:
                    - python >={{ python_min }}
                """
            ),
            [
                "python {{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python {{ python_min }}
                  run:
                    - python >={{ python_min }}
                """
            ),
            [
                "python {{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python {{ python_min }}
                  run:
                    - python >={{ python_min }}
                """
            ),
            [
                "python {{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python ={{ python_min }}
                  run:
                    - python >={{ python_min }}
                """
            ),
            [
                "python {{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python =={{ python_min }}
                  run:
                    - python >={{ python_min }}

                test:
                  requires:
                    - python {{ python_min }}
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python {{ python_min }}
                  run:
                    - python

                test:
                  requires:
                    - python {{ python_min }}
                """
            ),
            ["python >={{ python_min }}"],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python ={{ python_min }}
                  run:
                    - python

                test:
                  requires:
                    - python ={{ python_min }}
                """
            ),
            ["python >={{ python_min }}"],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python =={{ python_min }}
                  run:
                    - python

                test:
                  requires:
                    - python =={{ python_min }}
                """
            ),
            ["python >={{ python_min }}"],
        ),
        (
            textwrap.dedent(
                """
                {% set python_min = '3.7' %}

                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python {{ python_min }}
                  run:
                    - python >={{ python_min }}

                test:
                  requires:
                    - python {{ python_min }}
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                {% set python_min = '3.7' %}

                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python  {{ python_min }}
                  run:
                    - python  >={{ python_min }}

                test:
                  requires:
                    - python    {{ python_min }}
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                outputs:
                  - name: python-foo
                    build:
                      noarch: python

                    requirements:
                      host:
                        - python {{ python_min }}
                      run:
                        - python >={{ python_min }}

                    test:
                      requires:
                        - python {{ python_min }}
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                outputs:
                  - name: python-foo
                    build:
                      noarch: python

                    requirements:
                      host:
                        - python {{ python_min }}
                      run:
                        - python

                    test:
                      requires:
                        - python {{ python_min }}
                """
            ),
            ["python >={{ python_min }}"],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                outputs:
                  - name: python-foo
                    build:
                      noarch: python

                    requirements:
                      host:
                        - python {{ python_min }}
                      run:
                        - python >={{ python_min }}

                    test:
                      requires:
                        - python {{ python_min }}
                  - name: python-bar
                    build:
                      noarch: python

                    requirements:
                      - python

                    test:
                      requires:
                        - python
                """
            ),
            ["python {{ python_min }}"],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                outputs:
                  - name: python-foo
                    build:
                      noarch: python

                    requirements:
                      host:
                        - python {{ python_min }}
                      run:
                        - python >={{ python_min }}

                    test:
                      requires:
                        - python {{ python_min }}
                  - name: python-bar

                    requirements:
                      host:
                        - python
                      run:
                        - python

                    test:
                      requires:
                        - python
                """
            ),
            [],
        ),
    ],
)
@pytest.mark.parametrize("skip", [False, True])
def test_hint_noarch_python_use_python_min(
    meta_str,
    expected_hints,
    skip,
    tmp_path,
):
    if skip:
        with open(tmp_path / "conda-forge.yml", "w") as fh:
            fh.write(
                """
linter:
  skip:
    - hint_python_min
"""
            )

    meta = get_yaml().load(render_meta_yaml(meta_str))
    lints = []
    hints = []
    linter.run_conda_forge_specific(
        meta,
        str(tmp_path),
        lints,
        hints,
        recipe_version=0,
    )

    # make sure we have the expected hints
    if expected_hints and not skip:
        for expected_hint in expected_hints:
            assert any(expected_hint in hint for hint in hints), hints
    else:
        assert all("python_min" not in hint for hint in hints)


@pytest.mark.parametrize(
    "meta_str,expected_hints",
    [
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  run:
                    - python
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  run:
                    - python
                """
            ),
            [
                "python ${{ python_min }}.*",
                "python >=${{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python ${{ python_min }}.*
                  run:
                    - python >=${{ python_min }}

                tests:
                  - requirements:
                      run:
                        - python ${{ python_min }}.*
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python ${{ python_min }}.*
                  run:
                    - python >=${{ python_min }}

                tests:
                  - requirements:
                      run:
                        - python
                """
            ),
            [
                "tests[].python.python_version",
                "tests[].requirements.run",
                "python ${{ python_min }}.*",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - python ${{ python_min }}.*
                  run:
                    - python >=${{ python_min }}

                tests:
                  - python:
                      pip_check: false
                """
            ),
            [
                "tests[].python.python_version",
                "tests[].requirements.run",
                "python ${{ python_min }}.*",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                requirements:
                  run:
                    - if: blah
                      then: python
                      else: python 3.7
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  run:
                    - if: blah
                      then: python
                """
            ),
            [
                "python ${{ python_min }}.*",
                "python >=${{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - if: blah
                      then: blahblah
                      else: python ${{ python_min }}.*
                  run:
                    - python >=${{ python_min }}

                tests:
                  - requirements:
                      run:
                        - python ${{ python_min }}.*
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - if: blah
                      then: blahblah
                      else: python =${{ python_min }}
                  run:
                    - python >=${{ python_min }}

                tests:
                  - requirements:
                      run:
                        - python =${{ python_min }}
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                package:
                  name: python

                build:
                  noarch: python

                requirements:
                  host:
                    - if: blah
                      then: blahblah
                      else: python ==${{ python_min }}
                  run:
                    - python >=${{ python_min }}

                tests:
                  - requirements:
                      run:
                        - python ==${{ python_min }}
                """
            ),
            [],
        ),
        (
            """\
requirements:
  host:
    - python ${{ python_min }}
    - pip
    - setuptools
  run:
    - python >=${{ python_min }}
    - lxml >=4.2.1
    - numpy >=1.13.3
    - openbabel >=3.0.0
  run_constraints:
    - ImageMagick >=7.0
    - pymol-open-source >=2.3.0

tests:
  - python:
      imports:
        - plip
      python_version: ${{ python_min }}
      pip_check: false # it fails at detecting openbabel. see https://github.com/conda-forge/openbabel-feedstock/issues/49
  - script:
      - plip --help
    requirements:
      run:
        - python ${{ python_min }}.*
""",
            [],
        ),
        (
            textwrap.dedent(
                """
                recipe:
                  name: python

                outputs:
                  - package:
                      name: python-foo
                    build:
                      noarch: python
                    requirements:
                      host:
                        - if: blah
                          then: blahblah
                          else: python ${{ python_min }}.*
                      run:
                        - python >=${{ python_min }}

                    tests:
                      - requirements:
                          run:
                            - python ${{ python_min }}.*
                """
            ),
            [],
        ),
        (
            textwrap.dedent(
                """
                recipe:
                  name: python

                outputs:
                  - package:
                      name: python-foo
                    build:
                      noarch: python
                    requirements:
                      host:
                        - if: blah
                          then: blahblah
                          else: python
                      run:
                        - python >=${{ python_min }}

                    tests:
                      - requirements:
                          run:
                            - python ${{ python_min }}.*
                  - package:
                      name: python-bar
                    build:
                      noarch: python
                    requirements:
                      host:
                        - if: blah
                          then: blahblah
                          else: python ${{ python_min }}.*
                      run:
                        - python

                    tests:
                      - requirements:
                          run:
                            - python ${{ python_min }}.*
                """
            ),
            [
                "python ${{ python_min }}",
                "python >=${{ python_min }}",
            ],
        ),
        (
            textwrap.dedent(
                """
                recipe:
                  name: python

                outputs:
                  - package:
                      name: python-foo
                    build:
                      noarch: python
                    requirements:
                      host:
                        - if: blah
                          then: blahblah
                          else: python ${{ python_min }}.*
                      run:
                        - python >=${{ python_min }}

                    tests:
                      - requirements:
                          run:
                            - python ${{ python_min }}.*
                  - package:
                      name: python-bar
                    requirements:
                      host:
                        - if: blah
                          then: blahblah
                          else: python
                      run:
                        - python

                    tests:
                      - requirements:
                          run:
                            - python
                """
            ),
            [],
        ),
    ],
)
def test_hint_noarch_python_use_python_min_v1(
    meta_str,
    expected_hints,
):
    meta = get_yaml().load(meta_str)
    lints = []
    hints = []
    linter.run_conda_forge_specific(
        meta,
        None,
        lints,
        hints,
        recipe_version=1,
    )

    # make sure we have the expected hints
    if expected_hints:
        for expected_hint in expected_hints:
            assert any(expected_hint in hint for hint in hints), hints
    else:
        assert all("python_min" not in hint for hint in hints)


def test_hint_noarch_python_from_main_v1():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "recipe.yaml"), "w") as f:
            f.write(
                """\
context:
  name: plip
  version: 2.3.1

package:
  name: ${{ name|lower }}
  version: ${{ version }}

source:
  url: https://pypi.org/packages/source/${{ name[0] }}/${{ name }}/${{ name }}-${{ version }}.tar.gz
  sha256: 8d62c798b5ef6f3ae6ddd72e87c353bff8263e557dfa5f6ecf699cdf975f04ce

build:
  number: 1
  noarch: python
  script: python -m pip install . --no-build-isolation -vv
  python:
    entry_points:
      - plip = plip.plipcmd:main

requirements:
  host:
    - python ${{ python_min }}.*
    - pip
    - setuptools
  run:
    - python >=${{ python_min }}
    - lxml >=4.2.1
    - numpy >=1.13.3
    - openbabel >=3.0.0
  run_constraints:
    - ImageMagick >=7.0
    - pymol-open-source >=2.3.0

tests:
  - python:
      imports:
        - plip
      python_version: ${{ python_min }}
      pip_check: false # it fails at detecting openbabel. see https://github.com/conda-forge/openbabel-feedstock/issues/49
  - script:
      - plip --help
    requirements:
      run:
        - python ${{ python_min }}.*

about:
  license: GPL-2.0-only
  license_file: LICENSE.txt
  summary: Analyze non-covalent protein-ligand interactions in 3D structures
  description: |
    Protein-Ligand Interaction Profiler - Analyze and visualize non-covalent
    protein-ligand interactions in PDB files according to memo Salentin et al. (2015)
  homepage: https://github.com/pharmai/plip
  repository: https://github.com/pharmai/plip
  documentation: https://github.com/pharmai/plip/blob/master/DOCUMENTATION.md

extra:
  recipe-maintainers:
    - hadim
    - mikemhenry
"""
            )
        lints, hints = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert not any(
            "`noarch: python` recipes should usually follow the syntax in" in hint
            for hint in hints
        )


def test_lint_recipe_parses_ok():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "meta.yaml"), "w") as f:
            f.write(
                textwrap.dedent(
                    """
                    package:
                      name: foo

                    build:
                      number: 0

                    test:
                      imports:
                        - foo

                    about:
                      home: something
                      license: MIT
                      license_file: LICENSE
                      summary: a test recipe

                    extra:
                      recipe-maintainers:
                        - a
                        - b
                    """
                )
            )
        lints, hints = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert not any(
            lint.startswith(
                "The recipe is not parsable by any of the known recipe parsers"
            )
            for lint in lints
        ), lints
        assert not any(
            hint.startswith("The recipe is not parsable by parser") for hint in hints
        ), hints


def test_lint_recipe_parses_forblock():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "meta.yaml"), "w") as f:
            f.write(
                textwrap.dedent(
                    """
                    package:
                      name: foo
                    build:
                      number: 0
                    test:
                      imports:
                        {% for blah in blahs %}
                        - {{ blah }}
                        {% endfor %}
                    about:
                      home: something
                      license: MIT
                      license_file: LICENSE
                      summary: a test recipe
                    extra:
                      recipe-maintainers:
                          - a
                          - b
                    """
                )
            )
        lints, hints = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert not any(
            lint.startswith(
                "The recipe is not parsable by any of the known recipe parsers"
            )
            for lint in lints
        ), lints
        assert not any(
            hint.startswith("The recipe is not parsable by parser `conda-forge-tick")
            for hint in hints
        ), hints
        assert not any(
            hint.startswith("The recipe is not parsable by parser `conda-souschef")
            for hint in hints
        ), hints


def test_lint_recipe_parses_spacing():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "meta.yaml"), "w") as f:
            f.write(
                textwrap.dedent(
                    """
                    package:
                      name: foo
                    build:
                      number: 0
                    test:
                      imports:
                          - foo
                    about:
                      home: something
                      license: MIT
                      license_file: LICENSE
                      summary: a test recipe
                    extra:
                      recipe-maintainers:
                          - a
                          - b
                    """
                )
            )
        lints, hints = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert not any(
            lint.startswith(
                "The recipe is not parsable by any of the known recipe parsers"
            )
            for lint in lints
        ), lints
        assert not any(
            hint.startswith("The recipe is not parsable by parser `conda-forge-tick")
            for hint in hints
        ), hints
        assert not any(
            hint.startswith(
                "The recipe is not parsable by parser `conda-recipe-manager"
            )
            for hint in hints
        ), hints
        assert not any(
            hint.startswith("The recipe is not parsable by parser `conda-souschef")
            for hint in hints
        ), hints


def test_lint_recipe_parses_v1_spacing():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "recipe.yaml"), "w") as f:
            f.write(
                textwrap.dedent(
                    """
                    package:
                      name: blah

                    build:
                        number: ${{ build }}

                    about:
                      home: something
                      license: MIT
                      license_file: LICENSE
                      summary: a test recipe

                    extra:
                      recipe-maintainers:
                        - a
                        - b
                    """
                )
            )
        lints, hints = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert not any(
            lint.startswith(
                "The recipe is not parsable by any of the known recipe parsers"
            )
            for lint in lints
        ), lints
        assert not any(
            hint.startswith("The recipe is not parsable by parser `ruamel.yaml")
            for hint in hints
        ), hints


def test_lint_recipe_parses_v1_duplicate_keys():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "recipe.yaml"), "w") as f:
            f.write(
                textwrap.dedent(
                    """
                    package:
                      name: blah

                    build:
                      number: ${{ build }}
                      number: 42

                    about:
                      home: something
                      license: MIT
                      license_file: LICENSE
                      summary: a test recipe

                    extra:
                      recipe-maintainers:
                        - a
                        - b
                    """
                )
            )
        lints, hints = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert not any(
            lint.startswith(
                "The recipe is not parsable by any of the known recipe parsers"
            )
            for lint in lints
        ), lints
        assert not any(
            hint.startswith(
                "The recipe is not parsable by parser `conda-recipe-manager"
            )
            for hint in hints
        ), hints
        assert any(
            hint.startswith("The recipe is not parsable by parser `ruamel.yaml")
            for hint in hints
        ), hints


def test_lint_recipe_v1_invalid_schema_version():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "recipe.yaml"), "w") as f:
            f.write(
                textwrap.dedent(
                    """
                    schema_version: 2

                    package:
                      name: blah
                    """
                )
            )
        lints, hints = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert lints == ["Unsupported recipe.yaml schema version 2"]


@pytest.mark.parametrize(
    "text",
    [
        """
package:
    name: python

build:
    noarch: python

requirements:
    host:
      - python ${{ python_min }}
    run:
      - python >=${{ python_min }}

tests:
  - python:
      imports:
        - mypackage
      python_version: ${{ python_min }}.*
    """,
        """
package:
  name: python

build:
  noarch: python

requirements:
  host:
    - python ${{ python_min }}
  run:
    - python >=${{ python_min }}

tests:
  - python:
      imports:
        - mypackage
      python_version:
        - ${{ python_min }}.*
        - 3.13.*
    """,
    ],
)
def test_lint_recipe_v1_python_min_in_python_version(text):
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "recipe.yaml"), "w") as f:
            f.write(text)
        _, hints = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert not any(
            "`noarch: python` recipes should usually follow the syntax" in h
            for h in hints
        )


def test_lint_recipe_v1_comment_selectors():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "recipe.yaml"), "w") as f:
            f.write(
                textwrap.dedent(
                    """
                package:
                  name: test
                  version: 1.2.3

                build:
                  number: 0

                requirements:
                  host:
                    - foo  # [unix]
                    # check for false positives with strings that look like
                    # old-style (non-comment) selectors
                    - bar  =1.2.3 [build=${{ torch_proc_type }}*]
                  run:
                    - bar  =1.2.3 [build=${{ torch_proc_type }}*]  # [py==312]

                # this is some [comment]
                tests:
                  - script:
                      - false  # [linux64]
                      - true   # [osx or win]

                about:
                  summary: test
                  homepage: https://example.com
                  license: MIT
                  license_file: COPYING

                extra:
                  recipe-maintainers:
                    - a
                """
                )
            )
        lints, _ = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert lints == [
            "Selectors in comment form no longer work in v1 recipes. "
            "Instead, if / then / else maps must be used. "
            "See lines [10, 15, 20, 21]."
        ]


@pytest.mark.parametrize("filename", ["meta.yaml", "recipe.yaml"])
def test_version_zero(filename: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, filename), "w") as f:
            f.write(
                textwrap.dedent(
                    """
                package:
                  name: test
                  version: 0
                """
                )
            )
        lints, _ = linter.main(tmpdir, return_hints=True, conda_forge=True)
        assert "Package version is missing." not in lints


@pytest.mark.parametrize(
    "spec, result",
    [
        ("python", True),
        ("python 3.9", True),
        ("python 3.9 *cpython*", True),
        ("python 3.9=*cpython*", False),
        ("python =3.9=*cpython*", False),
        ("python=3.9=*cpython*", False),
        ("python malformed=*cpython*", False),
        ("python >= 3.9", False),
        ('{{ pin_subpackage("pkg-" ~ var, max_pin="x.x.x") }}', True),
        ("conda-verify  >=3.1.0", True),
        ("conda-verify  >=3.1.0   *_0", True),
        ("subpackage_pin blah 4.5", True),
        ("compatible_pin blah 345", True),
    ],
)
def test_bad_specs(spec, result):
    assert hints._ensure_spec_space_separated(spec) is result


@pytest.mark.parametrize(
    "spec, ok",
    [
        ("python", True),
        ("python 3.9", True),
        ("python 3.9 *cpython*", True),
        ("python 3.9=*cpython*", False),
        ("python =3.9=*cpython*", False),
        ("python=3.9=*cpython*", False),
        ("python malformed=*cpython*", False),
    ],
)
def test_bad_specs_report(tmp_path, spec, ok):
    (tmp_path / "meta.yaml").write_text(
        textwrap.dedent(
            f"""
            package:
                name: foo
            requirements:
                run:
                - {spec}
            outputs:
              - name: foo-bar
                requirements:
                  host:
                    - {spec}
            """
        )
    )

    _, hints = linter.main(tmp_path, return_hints=True)
    print(hints)
    assert (
        all("top-level output has some malformed specs" not in hint for hint in hints)
        is ok
    )
    assert (
        all("foo-bar output has some malformed specs" not in hint for hint in hints)
        is ok
    )


@pytest.mark.parametrize(
    "create_recipe_file,directory_param,expected_tool",
    [
        # recipe path passed
        (None, "recipe", CONDA_BUILD_TOOL),
        ("meta.yaml", "recipe", CONDA_BUILD_TOOL),
        ("recipe.yaml", "recipe", RATTLER_BUILD_TOOL),
        # no conda-forge.yml, incorrect path passed
        (None, ".", CONDA_BUILD_TOOL),
        ("meta.yaml", ".", CONDA_BUILD_TOOL),
        ("recipe.yaml", ".", CONDA_BUILD_TOOL),
    ],
)
def test_find_recipe_directory(
    tmp_path, create_recipe_file, directory_param, expected_tool
):
    """
    Test ``find_recipe_directory()`` without ``conda-forge.yml``

    When ``find_recipe_directory()`` is passed a directory with
    no ``conda-forge.yml``, and no ``--feedstock-directory`` is passed,
    it should just return the input directory and guess tool from files
    inside it.
    """

    tmp_path.joinpath("recipe").mkdir()
    if create_recipe_file is not None:
        tmp_path.joinpath("recipe", create_recipe_file).touch()

    assert linter.find_recipe_directory(str(tmp_path / directory_param), None) == (
        str(tmp_path / directory_param),
        expected_tool,
    )


@pytest.mark.parametrize("build_tool", [None, CONDA_BUILD_TOOL, RATTLER_BUILD_TOOL])
@pytest.mark.parametrize("recipe_dir", [None, "foo", "recipe"])
def test_find_recipe_directory_via_conda_forge_yml(tmp_path, build_tool, recipe_dir):
    """
    Test ``find_recipe_directory()`` with ``conda-forge.yml``

    When ``find_recipe_directory()`` is passed a directory with
    ``conda-forge.yml``, and no ``--feedstock-directory``, it should read
    both the recipe directory and the tool type from it.
    """

    # create all files to verify that format is taken from conda-forge.yml
    tmp_path.joinpath("recipe").mkdir()
    tmp_path.joinpath("recipe", "meta.yaml").touch()
    tmp_path.joinpath("recipe", "recipe.yaml").touch()

    with tmp_path.joinpath("conda-forge.yml").open("w") as f:
        if build_tool is not None:
            f.write(f"conda_build_tool: {build_tool}\n")
        if recipe_dir is not None:
            f.write(f"recipe_dir: {recipe_dir}\n")

    assert linter.find_recipe_directory(str(tmp_path), None) == (
        str(tmp_path / (recipe_dir or "recipe")),
        build_tool or CONDA_BUILD_TOOL,
    )


@pytest.mark.parametrize("build_tool", [None, CONDA_BUILD_TOOL, RATTLER_BUILD_TOOL])
@pytest.mark.parametrize("yaml_recipe_dir", [None, "foo", "recipe"])
@pytest.mark.parametrize("directory_param", [".", "recipe"])
def test_find_recipe_directory_with_feedstock_dir(
    tmp_path, build_tool, yaml_recipe_dir, directory_param
):
    """
    Test ``find_recipe_directory()`` with ``--feedstock-directory``

    When ``find_recipe_directory()`` is passed a ``--feedstock-directory``,
    it should read the tool type from it, but use the passed recipe
    directory.
    """

    # create all files to verify that format is taken from conda-forge.yml
    tmp_path.joinpath("recipe").mkdir()
    tmp_path.joinpath("recipe", "meta.yaml").touch()
    tmp_path.joinpath("recipe", "recipe.yaml").touch()

    with tmp_path.joinpath("conda-forge.yml").open("w") as f:
        if build_tool is not None:
            f.write(f"conda_build_tool: {build_tool}\n")
        if yaml_recipe_dir is not None:
            f.write(f"recipe_dir: {yaml_recipe_dir}\n")

    assert linter.find_recipe_directory(
        str(tmp_path / directory_param), str(tmp_path)
    ) == (
        str(tmp_path / directory_param),
        build_tool or CONDA_BUILD_TOOL,
    )


def test_cfyml_obsolete_os_version():
    expected_message = "The feedstock is lowering the image versions for one or more platforms: {'linux_64': 'cos7'}"

    with tmp_directory() as feedstock_dir:
        cfyml = os.path.join(feedstock_dir, "conda-forge.yml")
        recipe_dir = os.path.join(feedstock_dir, "recipe")
        os.makedirs(recipe_dir, exist_ok=True)
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                """
                package:
                  name: foo
                """
            )

        with open(cfyml, "w") as fh:
            fh.write(
                textwrap.dedent(
                    """
                    os_version:
                      linux_64: cos7
                    """
                )
            )

        _, hints = linter.main(recipe_dir, conda_forge=True, return_hints=True)
        assert any(expected_message in hint for hint in hints)


@pytest.mark.parametrize(
    "lstr,ok",
    [
        ("is_abi3", True),
        ("is_abi3 == 'true'", False),
        ("is_abi3 != 'true'", False),
        ("is_abi3 == 'false'", False),
        ("is_abi3 != 'false'", False),
        ('is_abi3=="true"', False),
        ('is_abi3!="true"', False),
        ('is_abi3  =="false"', False),
        ('is_abi3!=  "false"', False),
    ],
)
def test_is_abi3_bool_lint(lstr, ok):
    expected_message = "`is_abi3` variant variable is now a boolea"

    with tmp_directory() as recipe_dir:
        with open(os.path.join(recipe_dir, "meta.yaml"), "w") as fh:
            fh.write(
                f"""
                package:
                   name: foo
                requirements:
                  run:
                    # {lstr}
                    - python
                """
            )

        lints, _ = linter.main(recipe_dir, return_hints=True, conda_forge=True)
        if ok:
            assert not any(expected_message in lint for lint in lints)
        else:
            assert any(expected_message in lint for lint in lints)


if __name__ == "__main__":
    unittest.main()
