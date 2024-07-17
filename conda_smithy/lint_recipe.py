# -*- coding: utf-8 -*-

import copy
import fnmatch
import io
import itertools
import json
import os
import re
import requests
import shutil
import subprocess
import sys
from glob import glob
from inspect import cleandoc
from textwrap import indent

import github
from collections.abc import Sequence, Mapping
from pathlib import Path

from rattler_build_conda_compat import loader as rattler_loader

from conda_smithy import rattler_linter
from conda_smithy.configure_feedstock import _read_forge_config
from rattler_build_conda_compat.loader import parse_recipe_config_file

str_type = str


if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from conda.models.version import VersionOrder
from conda_build.metadata import (
    ensure_valid_license_family,
    FIELDS as cbfields,
)
from conda_smithy.validate_schema import validate_json_schema
from ruamel.yaml import CommentedSeq

from .utils import render_meta_yaml, get_yaml


FIELDS = copy.deepcopy(cbfields)

# Just in case 'extra' moves into conda_build
if "extra" not in FIELDS.keys():
    FIELDS["extra"] = {}

FIELDS["extra"]["recipe-maintainers"] = ()
FIELDS["extra"]["feedstock-name"] = ""

EXPECTED_SECTION_ORDER = [
    "package",
    "source",
    "build",
    "requirements",
    "test",
    "app",
    "outputs",
    "about",
    "extra",
]

REQUIREMENTS_ORDER = ["build", "host", "run"]

TEST_KEYS = {"imports", "commands"}
TEST_FILES = ["run_test.py", "run_test.sh", "run_test.bat", "run_test.pl"]


NEEDED_FAMILIES = ["gpl", "bsd", "mit", "apache", "psf"]

sel_pat = re.compile(r"(.+?)\s*(#.*)?\[([^\[\]]+)\](?(2).*)$")
jinja_pat = re.compile(r"\s*\{%\s*(set)\s+[^\s]+\s*=\s*[^\s]+\s*%\}")
JINJA_VAR_PAT = re.compile(r"{{(.*?)}}")

CONDA_BUILD_TOOL = "conda-build"
RATTLER_BUILD_TOOL = "rattler-build"


def get_section(parent, name, lints, is_rattler_build=False):
    if not is_rattler_build:
        return get_meta_section(parent, name, lints)
    else:
        return get_rattler_section(parent, name)


def get_meta_section(parent, name, lints):
    if name == "source":
        return get_list_section(parent, name, lints, allow_single=True)
    elif name == "outputs":
        return get_list_section(parent, name, lints)

    section = parent.get(name, {})
    if not isinstance(section, Mapping):
        lints.append(
            'The "{}" section was expected to be a dictionary, but '
            "got a {}.".format(name, type(section).__name__)
        )
        section = {}
    return section


def get_rattler_section(meta, name):
    # get rattler recipe.yaml section
    if name == "requirements":
        return rattler_loader.load_all_requirements(meta)
    elif name == "source":
        source = meta.get("source", [])
        if isinstance(source, Mapping):
            return [source]

    return meta.get(name, {})


def get_list_section(parent, name, lints, allow_single=False):
    section = parent.get(name, [])
    if allow_single and isinstance(section, Mapping):
        return [section]
    elif isinstance(section, Sequence) and not isinstance(section, str_type):
        return section
    else:
        msg = 'The "{}" section was expected to be a {}list, but got a {}.{}.'.format(
            name,
            "dictionary or a " if allow_single else "",
            type(section).__module__,
            type(section).__name__,
        )
        lints.append(msg)
        return [{}]


def lint_section_order(major_sections, lints, is_rattler_build=False):
    if not is_rattler_build:
        section_order_sorted = sorted(
            major_sections, key=EXPECTED_SECTION_ORDER.index
        )
    else:
        section_order_sorted = (
            rattler_linter.EXPECTED_MUTIPLE_OUTPUT_SECTION_ORDER
            if "outputs" in major_sections
            else rattler_linter.EXPECTED_SINGLE_OUTPUT_SECTION_ORDER
        )

    if major_sections != section_order_sorted:
        section_order_sorted_str = map(
            lambda s: "'%s'" % s, section_order_sorted
        )
        section_order_sorted_str = ", ".join(section_order_sorted_str)
        section_order_sorted_str = "[" + section_order_sorted_str + "]"
        lints.append(
            "The top level meta keys are in an unexpected order. "
            "Expecting {}.".format(section_order_sorted_str)
        )


def lint_about_contents(about_section, lints, is_rattler_build=False):
    expected_section = [
        "homepage" if is_rattler_build else "home",
        "license",
        "summary",
    ]
    for about_item in expected_section:
        # if the section doesn't exist, or is just empty, lint it.
        if not about_section.get(about_item, ""):
            lints.append(
                "The {} item is expected in the about section."
                "".format(about_item)
            )


def find_local_config_file(recipe_dir, filename):
    # support
    # 1. feedstocks
    # 2. staged-recipes with custom conda-forge.yaml in recipe
    # 3. staged-recipes
    found_filesname = (
        glob(os.path.join(recipe_dir, filename))
        or glob(
            os.path.join(recipe_dir, "..", filename),
        )
        or glob(
            os.path.join(recipe_dir, "..", "..", filename),
        )
    )

    return found_filesname[0] if found_filesname else None


def lintify_forge_yaml(recipe_dir=None) -> (list, list):
    if recipe_dir:
        forge_yaml_filename = (
            glob(os.path.join(recipe_dir, "..", "conda-forge.yml"))
            or glob(
                os.path.join(recipe_dir, "conda-forge.yml"),
            )
            or glob(
                os.path.join(recipe_dir, "..", "..", "conda-forge.yml"),
            )
        )
        if forge_yaml_filename:
            with open(forge_yaml_filename[0], "r") as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        forge_yaml = {}

    # This is where we validate against the jsonschema and execute our custom validators.
    return validate_json_schema(forge_yaml)


def lint_maintainers_section(extra_section, lints):
    if not extra_section.get("recipe-maintainers", []):
        lints.append(
            "The recipe could do with some maintainers listed in "
            "the `extra/recipe-maintainers` section."
        )

    if not (
        isinstance(extra_section.get("recipe-maintainers", []), Sequence)
        and not isinstance(
            extra_section.get("recipe-maintainers", []), str_type
        )
    ):
        lints.append("Recipe maintainers should be a json list.")


def lint_license(about_section, lints):
    license = about_section.get("license", "").lower()
    if "unknown" == license.strip():
        lints.append("The recipe license cannot be unknown.")


def lint_build_number(build_section, lints):
    if build_section.get("number", None) is None:
        lints.append("The recipe must have a `build/number` section.")


def lint_files_have_hashes(sources_section, lints):
    for source_section in sources_section:
        if "url" in source_section and not (
            {"sha1", "sha256", "md5"} & set(source_section.keys())
        ):
            lints.append(
                "When defining a source/url please add a sha256, sha1 "
                "or md5 checksum (sha256 preferably)."
            )


def lint_license_wording(about_section, lints):
    license = about_section.get("license", "").lower()
    if (
        "license" in license.lower()
        and "unlicense" not in license.lower()
        and "licenseref" not in license.lower()
        and "-license" not in license.lower()
    ):
        lints.append(
            "The recipe `license` should not include the word " '"License".'
        )


def lint_empty_line_of_the_file(recipe_dir, recipe_name, lints):
    if recipe_dir is not None and os.path.exists(recipe_name):
        with io.open(recipe_name, "r") as f:
            lines = f.read().split("\n")
        # Count the number of empty lines from the end of the file
        empty_lines = itertools.takewhile(lambda x: x == "", reversed(lines))
        end_empty_lines_count = len(list(empty_lines))
        if end_empty_lines_count > 1:
            lints.append(
                "There are {} too many lines.  "
                "There should be one empty line at the end of the "
                "file.".format(end_empty_lines_count - 1)
            )
        elif end_empty_lines_count < 1:
            lints.append(
                "There are too few lines.  There should be one empty "
                "line at the end of the file."
            )


def lint_lower_bound_python_version(
    noarch_value, run_reqs, outputs_section, lints
):
    if noarch_value == "python" and not outputs_section:
        for req in run_reqs:
            if (req.strip().split()[0] == "python") and (req != "python"):
                break
        else:
            lints.append(
                "noarch: python recipes are required to have a lower bound "
                "on the python version. Typically this means putting "
                "`python >=3.6` in **both** `host` and `run` but you should check "
                "upstream for the package's Python compatibility."
            )


def hint_pip_usage(build_section, hints):
    if "script" in build_section:
        scripts = build_section["script"]
        if isinstance(scripts, str):
            scripts = [scripts]
        for script in scripts:
            if "python setup.py install" in script:
                hints.append(
                    "Whenever possible python packages should use pip. "
                    "See https://conda-forge.org/docs/maintainer/adding_pkgs.html#use-pip"
                )


def hint_fixing_shellcheck_findings(recipe_dir, hints):
    shellcheck_enabled = False
    shell_scripts = []
    if recipe_dir:
        shell_scripts = glob(os.path.join(recipe_dir, "*.sh"))
        forge_yaml = find_local_config_file(recipe_dir, "conda-forge.yml")
        if shell_scripts and forge_yaml:
            with open(forge_yaml, "r") as fh:
                code = get_yaml().load(fh)
                shellcheck_enabled = code.get("shellcheck", {}).get(
                    "enabled", shellcheck_enabled
                )
    if shellcheck_enabled and shutil.which("shellcheck") and shell_scripts:
        MAX_SHELLCHECK_LINES = 50
        cmd = [
            "shellcheck",
            "--enable=all",
            "--shell=bash",
            # SC2154: var is referenced but not assigned,
            #         see https://github.com/koalaman/shellcheck/wiki/SC2154
            "--exclude=SC2154",
        ]

        p = subprocess.Popen(
            cmd + shell_scripts,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={
                "PATH": os.getenv("PATH")
            },  # exclude other env variables to protect against token leakage
        )
        sc_stdout, _ = p.communicate()

        if p.returncode == 1:
            # All files successfully scanned with some issues.
            findings = (
                sc_stdout.decode(sys.stdout.encoding)
                .replace("\r\n", "\n")
                .splitlines()
            )
            hints.append(
                "Whenever possible fix all shellcheck findings ('"
                + " ".join(cmd)
                + " recipe/*.sh -f diff | git apply' helps)"
            )
            hints.extend(findings[:50])
            if len(findings) > MAX_SHELLCHECK_LINES:
                hints.append(
                    "Output restricted, there are '%s' more lines."
                    % (len(findings) - MAX_SHELLCHECK_LINES)
                )
        elif p.returncode != 0:
            # Something went wrong.
            hints.append(
                "There have been errors while scanning with shellcheck."
            )


def hint_spdx(about_section, hints):
    import license_expression

    license = about_section.get("license", "")
    licensing = license_expression.Licensing()
    parsed_exceptions = []
    try:
        parsed_licenses = []
        parsed_licenses_with_exception = licensing.license_symbols(
            license.strip(), decompose=False
        )
        for l in parsed_licenses_with_exception:
            if isinstance(l, license_expression.LicenseWithExceptionSymbol):
                parsed_licenses.append(l.license_symbol.key)
                parsed_exceptions.append(l.exception_symbol.key)
            else:
                parsed_licenses.append(l.key)
    except license_expression.ExpressionError:
        parsed_licenses = [license]

    licenseref_regex = re.compile(r"^LicenseRef[a-zA-Z0-9\-.]*$")
    filtered_licenses = []
    for license in parsed_licenses:
        if not licenseref_regex.match(license):
            filtered_licenses.append(license)

    with open(
        os.path.join(os.path.dirname(__file__), "licenses.txt"), "r"
    ) as f:
        expected_licenses = f.readlines()
        expected_licenses = set([l.strip() for l in expected_licenses])
    with open(
        os.path.join(os.path.dirname(__file__), "license_exceptions.txt"), "r"
    ) as f:
        expected_exceptions = f.readlines()
        expected_exceptions = set([l.strip() for l in expected_exceptions])
    if set(filtered_licenses) - expected_licenses:
        hints.append(
            "License is not an SPDX identifier (or a custom LicenseRef) nor an SPDX license expression.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )
    if set(parsed_exceptions) - expected_exceptions:
        hints.append(
            "License exception is not an SPDX exception.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )


def lint_meta_tests(test_section, outputs_section, recipe_dir, lints, hints):
    if not any(key in TEST_KEYS for key in test_section):
        a_test_file_exists = recipe_dir is not None and any(
            os.path.exists(os.path.join(recipe_dir, test_file))
            for test_file in TEST_FILES
        )
        if not a_test_file_exists:
            has_outputs_test = False
            no_test_hints = []
            if outputs_section:
                for out in outputs_section:
                    test_out = get_section(out, "test", lints)
                    if any(key in TEST_KEYS for key in test_out):
                        has_outputs_test = True
                    elif test_out.get("script", "").endswith((".bat", ".sh")):
                        has_outputs_test = True
                    else:
                        no_test_hints.append(
                            "It looks like the '{}' output doesn't "
                            "have any tests.".format(out.get("name", "???"))
                        )

            if has_outputs_test:
                hints.extend(no_test_hints)
            else:
                lints.append("The recipe must have some tests.")


def lintify_recipe(
    meta,
    recipe_dir=None,
    conda_forge=False,
    is_rattler_build=False,
) -> (list, list):
    lints = []
    hints = []
    major_sections = list(meta.keys())

    # If the recipe_dir exists (no guarantee within this function) , we can
    # find the meta.yaml within it.
    recipe_fname = "meta.yaml" if not is_rattler_build else "recipe.yaml"
    meta_fname = os.path.join(recipe_dir or "", recipe_fname)

    sources_section = get_section(meta, "source", lints, is_rattler_build)
    build_section = get_section(meta, "build", lints, is_rattler_build)
    requirements_section = get_section(
        meta, "requirements", lints, is_rattler_build
    )
    if is_rattler_build:
        test_section = get_section(meta, "tests", lints, is_rattler_build)
    else:
        test_section = get_section(meta, "test", lints, is_rattler_build)
    about_section = get_section(meta, "about", lints, is_rattler_build)
    extra_section = get_section(meta, "extra", lints, is_rattler_build)
    package_section = get_section(meta, "package", lints, is_rattler_build)
    outputs_section = get_section(meta, "outputs", lints, is_rattler_build)
    if is_rattler_build:
        context_section = get_section(meta, "section", lints)

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    is_staged_recipes = recipe_dirname != "recipe"

    if not is_rattler_build:
        # 0: Top level keys should be expected
        unexpected_sections = []
        for section in major_sections:
            if section not in EXPECTED_SECTION_ORDER:
                lints.append(
                    "The top level meta key {} is unexpected".format(section)
                )
                unexpected_sections.append(section)

        for section in unexpected_sections:
            major_sections.remove(section)

    # 1: Top level meta.yaml keys should have a specific order.
    lint_section_order(major_sections, lints, is_rattler_build)

    # 2: The about section should have a home, license and summary.
    lint_about_contents(about_section, lints, is_rattler_build)

    # 3a: The recipe should have some maintainers.
    # 3b: Maintainers should be a list
    lint_maintainers_section(extra_section, lints)

    # 4: The recipe should have some tests.
    if is_rattler_build:
        test_lints, test_hints = rattler_linter.lint_recipe_tests(
            test_section, outputs_section
        )
        lints.extend(test_lints)
        hints.extend(test_hints)

    else:
        lint_meta_tests(
            test_section, outputs_section, recipe_dir, lints, hints
        )

    # 5: License cannot be 'unknown.'
    lint_license(about_section, lints)

    # 6: Selectors should be in a tidy form.
    if not is_rattler_build:
        if recipe_dir is not None and os.path.exists(meta_fname):
            bad_selectors, bad_lines = [], []
            pyXY_selectors_lint, pyXY_lines_lint = [], []
            pyXY_selectors_hint, pyXY_lines_hint = [], []
            # Good selectors look like ".*\s\s#\s[...]"
            good_selectors_pat = re.compile(r"(.+?)\s{2,}#\s\[(.+)\](?(2).*)$")
            # Look out for py27, py35 selectors; we prefer py==35
            pyXY_selectors_pat = re.compile(r".+#\s*\[.*?(py\d{2,3}).*\]")
            with io.open(meta_fname, "rt") as fh:
                for selector_line, line_number in selector_lines(fh):
                    if not good_selectors_pat.match(selector_line):
                        bad_selectors.append(selector_line)
                        bad_lines.append(line_number)
                    pyXY_matches = pyXY_selectors_pat.match(selector_line)
                    if pyXY_matches:
                        for pyXY in pyXY_matches.groups():
                            if int(pyXY[2:]) in (27, 34, 35, 36):
                                # py27, py35 and so on are ok up to py36 (included); only warn
                                pyXY_selectors_hint.append(selector_line)
                                pyXY_lines_hint.append(line_number)
                            else:
                                pyXY_selectors_lint.append(selector_line)
                                pyXY_lines_lint.append(line_number)
            if bad_selectors:
                lints.append(
                    "Selectors are suggested to take a "
                    "``<two spaces>#<one space>[<expression>]`` form."
                    " See lines {}".format(bad_lines)
                )
            if pyXY_selectors_hint:
                hints.append(
                    "Old-style Python selectors (py27, py34, py35, py36) are "
                    "deprecated. Instead, consider using the int ``py``. For "
                    "example: ``# [py>=36]``. See lines {}".format(
                        pyXY_lines_hint
                    )
                )
            if pyXY_selectors_lint:
                lints.append(
                    "Old-style Python selectors (py27, py35, etc) are only available "
                    "for Python 2.7, 3.4, 3.5, and 3.6. Please use explicit comparisons "
                    "with the integer ``py``, e.g. ``# [py==37]`` or ``# [py>=37]``. "
                    "See lines {}".format(pyXY_lines_lint)
                )

    # 7: The build section should have a build number.
    lint_build_number(build_section, lints)

    # 8: The build section should be before the run section in requirements.
    seen_requirements = [
        k for k in requirements_section if k in REQUIREMENTS_ORDER
    ]
    requirements_order_sorted = sorted(
        seen_requirements, key=REQUIREMENTS_ORDER.index
    )
    if seen_requirements != requirements_order_sorted:
        lints.append(
            "The `requirements/` sections should be defined "
            "in the following order: "
            + ", ".join(REQUIREMENTS_ORDER)
            + "; instead saw: "
            + ", ".join(seen_requirements)
            + "."
        )

    # 9: Files downloaded should have a hash.
    lint_files_have_hashes(sources_section, lints)

    # 10: License should not include the word 'license'.
    lint_license_wording(about_section, lints)

    # 11: There should be one empty line at the end of the file.
    lint_empty_line_of_the_file(recipe_dir, meta_fname, lints)

    # 12: License family must be valid (conda-build checks for that)
    if not is_rattler_build:
        try:
            ensure_valid_license_family(meta)
        except RuntimeError as e:
            lints.append(str(e))

    # 12a: License family must be valid (conda-build checks for that)
    if not is_rattler_build:
        license = about_section.get("license", "").lower()
        license_family = about_section.get("license_family", license).lower()
        license_file = about_section.get("license_file", None)
        if not license_file and any(
            f for f in NEEDED_FAMILIES if f in license_family
        ):
            lints.append("license_file entry is missing, but is required.")
    else:
        rattler_linter.lint_has_recipe_file(about_section, lints)

    # 13: Check that the recipe name is valid
    if not is_rattler_build:
        recipe_name = package_section.get("name", "").strip()
        if re.match(r"^[a-z0-9_\-.]+$", recipe_name) is None:
            lints.append(
                "Recipe name has invalid characters. only lowercase alpha, numeric, "
                "underscores, hyphens and dots allowed"
            )
    else:
        package_name_lint = rattler_linter.lint_package_name(
            package_section, context_section
        )
        if package_name_lint:
            lints.append(package_name_lint)

    # 14: Run conda-forge specific lints
    if conda_forge:
        run_conda_forge_specific(meta, recipe_dir, lints, hints)

    # 15: Check if we are using legacy patterns
    build_reqs = requirements_section.get("build", None)
    if build_reqs and ("numpy x.x" in build_reqs):
        lints.append(
            "Using pinned numpy packages is a deprecated pattern.  Consider "
            "using the method outlined "
            "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy)."
        )

    noarch_value = build_section.get("noarch")
    if not is_rattler_build:
        # 16: Subheaders should be in the allowed subheadings
        for section in major_sections:
            expected_subsections = FIELDS.get(section, [])
            if not expected_subsections:
                continue
            for subsection in get_section(meta, section, lints):
                if (
                    section != "source"
                    and section != "outputs"
                    and subsection not in expected_subsections
                ):
                    lints.append(
                        "The {} section contained an unexpected "
                        "subsection name. {} is not a valid subsection"
                        " name.".format(section, subsection)
                    )
                elif section == "source" or section == "outputs":
                    for source_subsection in subsection:
                        if source_subsection not in expected_subsections:
                            lints.append(
                                "The {} section contained an unexpected "
                                "subsection name. {} is not a valid subsection"
                                " name.".format(section, source_subsection)
                            )
        # 17: Validate noarch
        # noarch_value = build_section.get("noarch")
        if noarch_value is not None:
            valid_noarch_values = ["python", "generic"]
            if noarch_value not in valid_noarch_values:
                valid_noarch_str = "`, `".join(valid_noarch_values)
                lints.append(
                    "Invalid `noarch` value `{}`. Should be one of `{}`.".format(
                        noarch_value, valid_noarch_str
                    )
                )

    conda_build_config_filename = None
    if recipe_dir:
        conda_build_config_filename = find_local_config_file(
            recipe_dir, "conda_build_config.yaml"
        )

        if conda_build_config_filename:
            with open(conda_build_config_filename, "r") as fh:
                conda_build_config_keys = set(get_yaml().load(fh).keys())
        else:
            conda_build_config_keys = set()

        forge_yaml_filename = find_local_config_file(
            recipe_dir, "conda-forge.yml"
        )

        if forge_yaml_filename:
            with open(forge_yaml_filename, "r") as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        conda_build_config_keys = set()
        forge_yaml = {}

    # 18: noarch doesn't work with selectors for runtime dependencies
    if not is_rattler_build:
        if noarch_value is not None and os.path.exists(meta_fname):
            noarch_platforms = len(forge_yaml.get("noarch_platforms", [])) > 1
            with io.open(meta_fname, "rt") as fh:
                in_runreqs = False
                for line in fh:
                    line_s = line.strip()
                    if line_s == "host:" or line_s == "run:":
                        in_runreqs = True
                        runreqs_spacing = line[: -len(line.lstrip())]
                        continue
                    if line_s.startswith("skip:") and is_selector_line(line):
                        lints.append(
                            "`noarch` packages can't have skips with selectors. If "
                            "the selectors are necessary, please remove "
                            "`noarch: {}`.".format(noarch_value)
                        )
                        break
                    if in_runreqs:
                        if runreqs_spacing == line[: -len(line.lstrip())]:
                            in_runreqs = False
                            continue
                        if is_selector_line(
                            line,
                            allow_platforms=noarch_platforms,
                            allow_keys=conda_build_config_keys,
                        ):
                            lints.append(
                                "`noarch` packages can't have selectors. If "
                                "the selectors are necessary, please remove "
                                "`noarch: {}`.".format(noarch_value)
                            )
                            break
    else:
        raw_requirements_section = meta.get("requirements", {})
        lints.extend(
            rattler_linter.lint_usage_of_selectors_for_noarch(
                noarch_value, build_section, raw_requirements_section
            )
        )

    # 19: check version
    if not is_rattler_build:
        if package_section.get("version") is not None:
            ver = str(package_section.get("version"))
            try:
                VersionOrder(ver)
            except Exception:
                lints.append(
                    "Package version {} doesn't match conda spec".format(ver)
                )
    else:
        version_lint = rattler_linter.lint_package_version(
            package_section, context_section
        )
        if version_lint:
            lints.append(version_lint)

    if not is_rattler_build:
        # 20: Jinja2 variable definitions should be nice.
        if recipe_dir is not None and os.path.exists(meta_fname):
            bad_jinja = []
            bad_lines = []
            # Good Jinja2 variable definitions look like "{% set .+ = .+ %}"
            good_jinja_pat = re.compile(
                r"\s*\{%\s(set)\s[^\s]+\s=\s[^\s]+\s%\}"
            )
            with io.open(meta_fname, "rt") as fh:
                for jinja_line, line_number in jinja_lines(fh):
                    if not good_jinja_pat.match(jinja_line):
                        bad_jinja.append(jinja_line)
                        bad_lines.append(line_number)
            if bad_jinja:
                lints.append(
                    "Jinja2 variable definitions are suggested to "
                    "take a ``{{%<one space>set<one space>"
                    "<variable name><one space>=<one space>"
                    "<expression><one space>%}}`` form. See lines "
                    "{}".format(bad_lines)
                )

    # 21: Legacy usage of compilers
    if build_reqs and ("toolchain" in build_reqs):
        lints.append(
            "Using toolchain directly in this manner is deprecated.  Consider "
            "using the compilers outlined "
            "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers)."
        )

    # 22: Single space in pinned requirements
    for section, requirements in requirements_section.items():
        for requirement in requirements or []:
            if is_rattler_build:
                req = requirement
                symbol_to_check = "${{"
            else:
                req, _, _ = requirement.partition("#")
                symbol_to_check = "{{"

            if symbol_to_check in req:
                continue
            parts = req.split()
            if len(parts) > 2 and parts[1] in [
                "!=",
                "=",
                "==",
                ">",
                "<",
                "<=",
                ">=",
            ]:
                # check for too many spaces
                lints.append(
                    (
                        "``requirements: {section}: {requirement}`` should not "
                        "contain a space between relational operator and the version, i.e. "
                        "``{name} {pin}``"
                    ).format(
                        section=section,
                        requirement=requirement,
                        name=parts[0],
                        pin="".join(parts[1:]),
                    )
                )
                continue
            # check that there is a space if there is a pin
            bad_char_idx = [(parts[0].find(c), c) for c in "><="]
            bad_char_idx = [bci for bci in bad_char_idx if bci[0] >= 0]
            if bad_char_idx:
                bad_char_idx.sort()
                i = bad_char_idx[0][0]
                lints.append(
                    (
                        "``requirements: {section}: {requirement}`` must "
                        "contain a space between the name and the pin, i.e. "
                        "``{name} {pin}``"
                    ).format(
                        section=section,
                        requirement=requirement,
                        name=parts[0][:i],
                        pin=parts[0][i:] + "".join(parts[1:]),
                    )
                )
                continue

    # 23: non noarch builds shouldn't use version constraints on python and r-base
    check_languages = ["python", "r-base"]
    host_reqs = requirements_section.get("host") or []
    run_reqs = requirements_section.get("run") or []
    for language in check_languages:
        if noarch_value is None and not outputs_section:
            filtered_host_reqs = [
                req
                for req in host_reqs
                if req.partition(" ")[0] == str(language)
            ]
            filtered_run_reqs = [
                req
                for req in run_reqs
                if req.partition(" ")[0] == str(language)
            ]
            if filtered_host_reqs and not filtered_run_reqs:
                lints.append(
                    "If {0} is a host requirement, it should be a run requirement.".format(
                        str(language)
                    )
                )
            for reqs in [filtered_host_reqs, filtered_run_reqs]:
                if str(language) in reqs:
                    continue
                for req in reqs:
                    constraint = req.split(" ", 1)[1]
                    if constraint.startswith(">") or constraint.startswith(
                        "<"
                    ):
                        lints.append(
                            "Non noarch packages should have {0} requirement without any version constraints.".format(
                                str(language)
                            )
                        )

    # 24: jinja2 variable references should be {{<one space>var<one space>}}
    if recipe_dir is not None and os.path.exists(meta_fname):
        bad_vars = []
        bad_lines = []
        jinja_pattern = (
            JINJA_VAR_PAT
            if not is_rattler_build
            else rattler_linter.JINJA_VAR_PAT
        )
        with io.open(meta_fname, "rt") as fh:
            for i, line in enumerate(fh.readlines()):
                for m in jinja_pattern.finditer(line):
                    if m.group(1) is not None:
                        var = m.group(1)
                        if var != " %s " % var.strip():
                            bad_vars.append(m.group(1).strip())
                            bad_lines.append(i + 1)
        if bad_vars:
            hint_message = (
                "``{{<one space><variable name><one space>}}``"
                if not is_rattler_build
                else "``${{<one space><variable name><one space>}}``"
            )
            hints.append(
                "Jinja2 variable references are suggested to "
                f"take a {hint_message}"
                " form. See lines %s." % (bad_lines,)
            )

    # 25: require a lower bound on python version
    lint_lower_bound_python_version(
        noarch_value, run_reqs, outputs_section, lints
    )

    # 26: pin_subpackage is for subpackages and pin_compatible is for
    # non-subpackages of the recipe. Contact @carterbox for troubleshooting
    # this lint.
    subpackage_names = []
    for out in outputs_section:
        if "name" in out:
            subpackage_names.append(out["name"])  # explicit
    if "name" in package_section:
        subpackage_names.append(package_section["name"])  # implicit

    def check_pins(pinning_section):
        if pinning_section is None:
            return
        filter_pin = (
            "pin_compatible*" if is_rattler_build else "compatible_pin*"
        )
        for pin in fnmatch.filter(pinning_section, filter_pin):
            if pin.split()[1] in subpackage_names:
                lints.append(
                    "pin_subpackage should be used instead of"
                    f" pin_compatible for `{pin.split()[1]}`"
                    " because it is one of the known outputs of this recipe:"
                    f" {subpackage_names}."
                )
        filter_pin = (
            "pin_subpackage*" if is_rattler_build else "subpackage_pin*"
        )
        for pin in fnmatch.filter(pinning_section, filter_pin):
            if pin.split()[1] not in subpackage_names:
                lints.append(
                    "pin_compatible should be used instead of"
                    f" pin_subpackage for `{pin.split()[1]}`"
                    " because it is not a known output of this recipe:"
                    f" {subpackage_names}."
                )

    def check_pins_build_and_requirements(top_level):
        if not is_rattler_build:
            if "build" in top_level and "run_exports" in top_level["build"]:
                check_pins(top_level["build"]["run_exports"])
            if (
                "requirements" in top_level
                and "run" in top_level["requirements"]
            ):
                check_pins(top_level["requirements"]["run"])
            if (
                "requirements" in top_level
                and "host" in top_level["requirements"]
            ):
                check_pins(top_level["requirements"]["host"])
        else:
            if (
                "requirements" in top_level
                and "run_exports" in top_level["requirements"]
            ):
                if "strong" in top_level["requirements"]["run_exports"]:
                    check_pins(
                        top_level["requirements"]["run_exports"]["strong"]
                    )
                else:
                    check_pins(top_level["requirements"]["run_exports"])

    check_pins_build_and_requirements(meta)
    for out in outputs_section:
        check_pins_build_and_requirements(out)

    # 27: Check usage of whl files as a source
    pure_python_wheel_urls = []
    compiled_wheel_urls = []
    # We could iterate on `sources_section`, but that might miss platform specific selector lines
    # ... so raw meta.yaml and regex it is...
    pure_python_wheel_re = re.compile(r".*[:-]\s+(http.*-none-any\.whl)\s+.*")
    wheel_re = re.compile(r".*[:-]\s+(http.*\.whl)\s+.*")
    if recipe_dir is not None and os.path.exists(meta_fname):
        with open(meta_fname, "rt") as f:
            for line in f:
                if match := pure_python_wheel_re.search(line):
                    pure_python_wheel_urls.append(match.group(1))
                elif match := wheel_re.search(line):
                    compiled_wheel_urls.append(match.group(1))
    if compiled_wheel_urls:
        formatted_urls = ", ".join([f"`{url}`" for url in compiled_wheel_urls])
        lints.append(
            f"Detected compiled wheel(s) in source: {formatted_urls}. "
            "This is disallowed. All packages should be built from source except in "
            "rare and exceptional cases."
        )
    if pure_python_wheel_urls:
        formatted_urls = ", ".join(
            [f"`{url}`" for url in pure_python_wheel_urls]
        )
        if noarch_value == "python":  # this is ok, just hint
            hints.append(
                f"Detected pure Python wheel(s) in source: {formatted_urls}. "
                "This is generally ok for pure Python wheels and noarch=python "
                "packages but it's preferred to use a source distribution (sdist) if possible."
            )
        else:
            lints.append(
                f"Detected pure Python wheel(s) in source: {formatted_urls}. "
                "This is discouraged. Please consider using a source distribution (sdist) instead."
            )

    # 28: Check that Rust licenses are bundled.
    rust_compiler = (
        "{{ compiler('rust') }}"
        if not is_rattler_build
        else "${{ compiler('rust') }}"
    )
    if build_reqs and (rust_compiler in build_reqs):
        if "cargo-bundle-licenses" not in build_reqs:
            lints.append(
                "Rust packages must include the licenses of the Rust dependencies. "
                "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust"
            )

    # 29: Check that go licenses are bundled.
    go_compiler = (
        "{{ compiler('go') }}"
        if not is_rattler_build
        else "${{ compiler('go') }}"
    )
    if build_reqs and (go_compiler in build_reqs):
        if "go-licenses" not in build_reqs:
            lints.append(
                "Go packages must include the licenses of the Go dependencies. "
                "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go"
            )

    # hints
    # 1: suggest pip
    hint_pip_usage(build_section, hints)

    # 2: suggest python noarch (skip on feedstocks)
    if (
        noarch_value is None
        and build_reqs
        and not any(["_compiler_stub" in b for b in build_reqs])
        and ("pip" in build_reqs)
        and (is_staged_recipes or not conda_forge)
    ):
        if is_rattler_build:
            noarch_hints = rattler_linter.hint_noarch_usage(
                build_section, raw_requirements_section
            )
            hints.extend(noarch_hints)
        else:
            with io.open(meta_fname, "rt") as fh:
                in_runreqs = False
                no_arch_possible = True
                for line in fh:
                    line_s = line.strip()
                    if line_s == "host:" or line_s == "run:":
                        in_runreqs = True
                        runreqs_spacing = line[: -len(line.lstrip())]
                        continue
                    if line_s.startswith("skip:") and is_selector_line(line):
                        no_arch_possible = False
                        break
                    if in_runreqs:
                        if runreqs_spacing == line[: -len(line.lstrip())]:
                            in_runreqs = False
                            continue
                        if is_selector_line(line):
                            no_arch_possible = False
                            break
                if no_arch_possible:
                    hints.append(
                        "Whenever possible python packages should use noarch. "
                        "See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds"
                    )

    # 3: suggest fixing all recipe/*.sh shellcheck findings
    hint_fixing_shellcheck_findings(recipe_dir, hints)

    # 4: Check for SPDX
    hint_spdx(about_section, hints)

    # 5: stdlib-related hints
    global_build_reqs = requirements_section.get("build") or []
    global_run_reqs = requirements_section.get("run") or []
    if not is_rattler_build:
        global_constraints = requirements_section.get("run_constrained") or []

    build_hint = (
        '`{{ stdlib("c") }}`'
        if not is_rattler_build
        else '`${{ stdlib("c") }}`'
    )
    stdlib_hint = (
        "This recipe is using a compiler, which now requires adding a build "
        f"dependence on {build_hint} as well. Note that this rule applies to "
        "each output of the recipe using a compiler. For further details, please "
        "see https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    if not is_rattler_build:
        pat_compiler_stub = re.compile(
            "(m2w64_)?(c|cxx|fortran|rust)_compiler_stub"
        )
    else:
        pat_compiler_stub = re.compile(r"^\${{ compiler\(")
    outputs = get_section(
        meta, "outputs", lints, is_rattler_build=is_rattler_build
    )
    output_reqs = [x.get("requirements", {}) for x in outputs]

    # deal with cb2 recipes (no build/host/run distinction)
    if not is_rattler_build:
        output_reqs = [
            {"host": x, "run": x} if isinstance(x, CommentedSeq) else x
            for x in output_reqs
        ]

    # collect output requirements
    output_build_reqs = [x.get("build", []) or [] for x in output_reqs]
    output_run_reqs = [x.get("run", []) or [] for x in output_reqs]
    if not is_rattler_build:
        output_contraints = [
            x.get("run_constrained", []) or [] for x in output_reqs
        ]

    # aggregate as necessary
    all_build_reqs = [global_build_reqs] + output_build_reqs
    all_build_reqs_flat = global_build_reqs
    all_run_reqs_flat = global_run_reqs
    if not is_rattler_build:
        all_contraints_flat = global_constraints

    [all_build_reqs_flat := all_build_reqs_flat + x for x in output_build_reqs]
    [all_run_reqs_flat := all_run_reqs_flat + x for x in output_run_reqs]

    if not is_rattler_build:
        [
            all_contraints_flat := all_contraints_flat + x
            for x in output_contraints
        ]

    # this check needs to be done per output --> use separate (unflattened) requirements
    for build_reqs in all_build_reqs:
        has_compiler = any(pat_compiler_stub.match(rq) for rq in build_reqs)
        stdlib_stub = "c_stdlib_stub" if not is_rattler_build else "${{ stdlib"
        if has_compiler and stdlib_stub not in build_reqs:
            if stdlib_hint not in hints:
                hints.append(stdlib_hint)

    sysroot_hint_build = (
        '`{{ stdlib("c") }}`'
        if not is_rattler_build
        else '`${{ stdlib("c") }}`'
    )
    sysroot_hint = (
        "You're setting a requirement on sysroot_linux-<arch> directly; this should "
        f"now be done by adding a build dependence on {sysroot_hint_build}, and "
        "overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for the "
        "respective platform as necessary. For further details, please see "
        "https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    pat_sysroot = re.compile(r"sysroot_linux.*")
    if any(pat_sysroot.match(req) for req in all_build_reqs_flat):
        if sysroot_hint not in hints:
            hints.append(sysroot_hint)

    osx_hint = (
        "You're setting a constraint on the `__osx` virtual package directly; this "
        f"should now be done by adding a build dependence on {sysroot_hint_build}, "
        "and overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for "
        "the respective platform as necessary. For further details, please see "
        "https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    if not is_rattler_build:
        to_check = all_run_reqs_flat + all_contraints_flat
    else:
        to_check = all_run_reqs_flat

    if any(req.startswith("__osx >") for req in to_check):
        if osx_hint not in hints:
            hints.append(osx_hint)

    # stdlib issues in CBC ( conda-build-config )
    cbc_osx = {}
    if not is_rattler_build:
        cbc_lines = []
        if conda_build_config_filename:
            with open(conda_build_config_filename, "r") as fh:
                cbc_lines = fh.readlines()
    elif is_rattler_build and recipe_dir:
        platform_namespace = {
            "unix": True,
            "osx": True,
            "linux": False,
            "win": False,
        }
        variants_path = os.path.join(Path(recipe_dir), "variants.yaml")
        if os.path.exists(variants_path):
            cbc_osx = parse_recipe_config_file(
                variants_path, platform_namespace, allow_missing_selector=True
            )

    # filter on osx-relevant lines
    if not is_rattler_build:
        pat = re.compile(
            r"^([^:\#]*?)\s+\#\s\[.*(not\s(osx|unix)|(?<!not\s)(linux|win)).*\]\s*$"
        )
        # remove lines with selectors that don't apply to osx, i.e. if they contain
        # "not osx", "not unix", "linux" or "win"; this also removes trailing newlines.
        # the regex here doesn't handle `or`-conjunctions, but the important thing for
        # having a valid yaml after filtering below is that we avoid filtering lines with
        # a colon (`:`), meaning that all yaml keys "survive". As an example, keys like
        # c_stdlib_version can have `or`'d selectors, even if all values are arch-specific.
        cbc_lines_osx = [pat.sub("", x) for x in cbc_lines]
        cbc_content_osx = "\n".join(cbc_lines_osx)
        cbc_osx = get_yaml().load(cbc_content_osx) or {}
        # filter None values out of cbc_osx dict, can appear for example with
        # ```
        # c_stdlib_version:  # [unix]
        #   - 2.17           # [linux]
        #   # note lack of osx
        # ```

    cbc_osx = dict(filter(lambda item: item[1] is not None, cbc_osx.items()))

    def sort_osx(versions):
        # we need to have a known order for [x64, arm64]; in the absence of more
        # complicated regex processing, we assume that if there are two versions
        # being specified, the higher one is osx-arm64.
        if len(versions) == 2:
            if VersionOrder(str(versions[0])) > VersionOrder(str(versions[1])):
                versions = versions[::-1]
        return versions

    baseline_version = ["10.13", "11.0"]
    v_stdlib = sort_osx(cbc_osx.get("c_stdlib_version", baseline_version))
    macdt = sort_osx(cbc_osx.get("MACOSX_DEPLOYMENT_TARGET", baseline_version))
    sdk = sort_osx(cbc_osx.get("MACOSX_SDK_VERSION", baseline_version))

    if {"MACOSX_DEPLOYMENT_TARGET", "c_stdlib_version"} <= set(cbc_osx.keys()):
        # both specified, check that they match
        if len(v_stdlib) != len(macdt):
            # if lengths aren't matching, assume it's a legal combination
            # where one key is specified for less arches than the other and
            # let the rerender deal with the details
            pass
        else:
            mismatch_hint = (
                "Conflicting specification for minimum macOS deployment target!\n"
                "If your conda_build_config.yaml sets `MACOSX_DEPLOYMENT_TARGET`, "
                "please change the name of that key to `c_stdlib_version`!\n"
                "Continuing with `max(c_stdlib_version, MACOSX_DEPLOYMENT_TARGET)`."
            )
            merged_dt = []
            for v_std, v_mdt in zip(v_stdlib, macdt):
                # versions with a single dot may have been read as floats
                v_std, v_mdt = str(v_std), str(v_mdt)
                if VersionOrder(v_std) != VersionOrder(v_mdt):
                    if mismatch_hint not in hints:
                        hints.append(mismatch_hint)
                merged_dt.append(
                    v_mdt
                    if VersionOrder(v_std) < VersionOrder(v_mdt)
                    else v_std
                )
            cbc_osx["merged"] = merged_dt
    elif "MACOSX_DEPLOYMENT_TARGET" in cbc_osx.keys():
        cbc_osx["merged"] = macdt
        # only MACOSX_DEPLOYMENT_TARGET, should be renamed
        deprecated_dt = (
            "In your conda_build_config.yaml, please change the name of "
            "`MACOSX_DEPLOYMENT_TARGET`, to `c_stdlib_version`!"
        )
        if deprecated_dt not in hints:
            hints.append(deprecated_dt)
    elif "c_stdlib_version" in cbc_osx.keys():
        cbc_osx["merged"] = v_stdlib
        # only warn if version is below baseline
        outdated_hint = (
            "You are setting `c_stdlib_version` below the current global baseline "
            "in conda-forge (10.13). If this is your intention, you also need to "
            "override `MACOSX_DEPLOYMENT_TARGET` (with the same value) locally."
        )
        if len(v_stdlib) == len(macdt):
            # if length matches, compare individually
            for v_std, v_mdt in zip(v_stdlib, macdt):
                if VersionOrder(str(v_std)) < VersionOrder(str(v_mdt)):
                    if outdated_hint not in hints:
                        hints.append(outdated_hint)
        elif len(v_stdlib) == 1:
            # if length doesn't match, only warn if a single stdlib version
            # is lower than _all_ baseline deployment targets
            if all(
                VersionOrder(str(v_stdlib[0])) < VersionOrder(str(v_mdt))
                for v_mdt in macdt
            ):
                if outdated_hint not in hints:
                    hints.append(outdated_hint)

    # warn if SDK is lower than merged v_stdlib/macdt
    merged_dt = cbc_osx.get("merged", baseline_version)
    sdk_hint = (
        "You are setting `MACOSX_SDK_VERSION` below `c_stdlib_version`, "
        "in conda_build_config.yaml which is not possible! Please ensure "
        "`MACOSX_SDK_VERSION` is at least `c_stdlib_version` "
        "(you can leave it out if it is equal).\n"
        "If you are not setting `c_stdlib_version` yourself, this means "
        "you are requesting a version below the current global baseline in "
        "conda-forge (10.13). If this is the intention, you also need to "
        "override `c_stdlib_version` and `MACOSX_DEPLOYMENT_TARGET` locally."
    )
    if len(sdk) == len(merged_dt):
        # if length matches, compare individually
        for v_sdk, v_mdt in zip(sdk, merged_dt):
            # versions with a single dot may have been read as floats
            v_sdk, v_mdt = str(v_sdk), str(v_mdt)
            if VersionOrder(v_sdk) < VersionOrder(v_mdt):
                if sdk_hint not in hints:
                    hints.append(sdk_hint)
    elif len(sdk) == 1:
        # if length doesn't match, only warn if a single SDK version
        # is lower than _all_ merged deployment targets
        if all(
            VersionOrder(str(sdk[0])) < VersionOrder(str(v_mdt))
            for v_mdt in merged_dt
        ):
            if sdk_hint not in hints:
                hints.append(sdk_hint)

    return lints, hints


def lintify_recipe_yaml(
    meta,
    recipe_dir=None,
    conda_forge=False,
) -> (list, list):
    lints = []
    hints = []
    major_sections = list(meta.keys())

    # If the recipe_dir exists (no guarantee within this function) , we can
    # find the recipe.yaml within it.
    recipe_fname = os.path.join(recipe_dir or "", "recipe.yaml")

    sources_section = get_section(meta, "source", lints)
    build_section = meta.get("build", {})
    requirements_section = rattler_loader.load_all_requirements(meta)
    test_section = meta.get("tests", {})
    about_section = meta.get("about", {})
    extra_section = meta.get("extra", {})
    package_section = meta.get("package", {})
    context_section = meta.get("context", {})
    outputs_section = meta.get("outputs", {})

    noarch_value = build_section.get("noarch")
    run_reqs = requirements_section.get("run", [])

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    is_staged_recipes = recipe_dirname != "recipe"

    rattler_linter.lint_section_order(major_sections, lints)

    rattler_linter.lint_about_contents(about_section, lints)

    # 3a: The recipe should have some maintainers.
    # 3b: Maintainers should be a list
    lint_maintainers_section(extra_section, lints)

    # 4: The recipe should have some tests.
    test_lints, test_hints = rattler_linter.lint_recipe_tests(
        test_section, outputs_section
    )
    lints.extend(test_lints)
    hints.extend(test_hints)

    # 5: License cannot be 'unknown.'
    lint_license(about_section, lints)

    # 7: The build section should have a build number.
    lint_build_number(build_section, lints)

    # 8: The build section should be before the run section in requirements.
    rattler_linter.lint_requirements_order(requirements_section, lints)

    # 9: Files downloaded should have a hash.
    lint_files_have_hashes(sources_section, lints)

    # 10: License should not include the word 'license'.
    lint_license_wording(about_section, lints)

    # 11: There should be one empty line at the end of the file.
    lint_empty_line_of_the_file(recipe_dir, recipe_fname, lints)

    # 12a: License family must be valid (conda-build checks for that)
    rattler_linter.lint_has_recipe_file(about_section, lints)

    # 13: Check that the recipe name is valid
    lints.append(
        rattler_linter.lint_package_name(package_section, context_section)
    )

    # 14: Run conda-forge specific lints
    if conda_forge:
        run_conda_forge_specific(
            meta, recipe_dir, lints, hints, rattler_lint=True
        )

    # 15: Check if we are using legacy patterns
    rattler_linter.lint_legacy_patterns(requirements_section)

    # 18: noarch doesn't work with selectors for runtime dependencies
    raw_requirements_section = meta.get("requirements", {})
    lints.extend(
        rattler_linter.lint_usage_of_selectors_for_noarch(
            noarch_value, build_section, raw_requirements_section
        )
    )

    # 19: check version
    lints.append(
        rattler_linter.lint_package_version(package_section, context_section)
    )

    # 21: Legacy usage of compilers
    build_reqs = requirements_section.get("build", None)
    lints.append(rattler_linter.lint_legacy_compilers(build_reqs))

    # 22: Single space in pinned requirements
    lints.extend(
        rattler_linter.lint_usage_of_single_space_in_pinned_requirements(
            requirements_section
        )
    )

    # 23: non noarch builds shouldn't use version constraints on python and r-base
    if noarch_value is None and not outputs_section:
        lints.extend(
            rattler_linter.lint_non_noarch_dont_constrain_python_and_rbase(
                requirements_section
            )
        )

    # 24: jinja2 variable references should be {{<one space>var<one space>}}
    jinja_hints = rattler_linter.lint_variable_reference_should_have_space(
        recipe_dir=recipe_dir, recipe_file=recipe_fname
    )
    hints.extend(jinja_hints)

    # 25: require a lower bound on python version
    lint_lower_bound_python_version(
        noarch_value, run_reqs, outputs_section, lints
    )

    # 26: pin_subpackage is for subpackages and pin_compatible is for
    # non-subpackages of the recipe. Contact @carterbox for troubleshooting
    subpackage_names = []
    for out in outputs_section:
        if "name" in out:
            subpackage_names.append(out["name"])  # explicit
    if "name" in package_section:
        subpackage_names.append(package_section["name"])  # implicit

    def check_pins(pinning_section):
        if pinning_section is None:
            return
        for pin in fnmatch.filter(pinning_section, "${{ pin_compatible(*"):
            pin_func = pin.split()[1]
            pin_name = (
                pin_func.lstrip("pin_compatible")
                .lstrip("(")
                .rstrip(")")
                .split(",")[0]
            )
            if pin_name in subpackage_names:
                lints.append(
                    "pin_subpackage should be used instead of"
                    f" pin_compatible for `{pin.split()[1]}`"
                    " because it is one of the known outputs of this recipe:"
                    f" {subpackage_names}."
                )
        for pin in fnmatch.filter(pinning_section, "${{ pin_subpackage*"):
            pin_func = pin.split()[1]
            pin_name = (
                pin_func.lstrip("pin_subpackage")
                .lstrip("(")
                .rstrip(")")
                .split(",")[0]
            )
            if pin.split()[1] not in subpackage_names:
                lints.append(
                    "pin_compatible should be used instead of"
                    f" pin_subpackage for `{pin.split()[1]}`"
                    " because it is not a known output of this recipe:"
                    f" {subpackage_names}."
                )

    def check_pins_build_and_requirements(top_level):
        if (
            "requirements" in top_level
            and "run_exports" in top_level["requirements"]
        ):
            if "strong" in top_level["requirements"]["run_exports"]:
                check_pins(top_level["requirements"]["run_exports"]["strong"])
            else:
                check_pins(top_level["requirements"]["run_exports"])

    check_pins_build_and_requirements(meta)
    for out in outputs_section:
        check_pins_build_and_requirements(out)

    # hints
    # 1: suggest pip
    hint_pip_usage(build_section, hints)

    # 2: suggest python noarch (skip on feedstocks)
    if noarch_value is None and (is_staged_recipes or not conda_forge):
        noarch_hints = rattler_linter.hint_noarch_usage(
            build_section, raw_requirements_section
        )
        hints.extend(noarch_hints)

    # 3: suggest fixing all recipe/*.sh shellcheck findings
    hint_fixing_shellcheck_findings(recipe_dir, hints)

    # 4: Check for SPDX
    hint_spdx(about_section, hints)

    lints = [lint for lint in lints if lint]
    hints = [hint for hint in hints if hint]

    return lints, hints


def run_conda_forge_specific(
    meta, recipe_dir, lints, hints, rattler_lint=False
):
    gh = github.Github(os.environ["GH_TOKEN"])

    # Retrieve sections from meta
    package_section = get_section(
        meta, "package", lints, is_rattler_build=rattler_lint
    )
    extra_section = get_section(
        meta, "extra", lints, is_rattler_build=rattler_lint
    )
    sources_section = get_section(
        meta, "source", lints, is_rattler_build=rattler_lint
    )
    requirements_section = get_section(
        meta, "requirements", lints, is_rattler_build=rattler_lint
    )
    outputs_section = get_section(
        meta, "outputs", lints, is_rattler_build=rattler_lint
    )

    # Fetch list of recipe maintainers
    maintainers = extra_section.get("recipe-maintainers", [])

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    recipe_name = package_section.get("name", "").strip()
    is_staged_recipes = recipe_dirname != "recipe"

    # 1: Check that the recipe does not exist in conda-forge or bioconda
    if is_staged_recipes and recipe_name:
        cf = gh.get_user(os.getenv("GH_ORG", "conda-forge"))

        for name in set(
            [
                recipe_name,
                recipe_name.replace("-", "_"),
                recipe_name.replace("_", "-"),
            ]
        ):
            try:
                if cf.get_repo("{}-feedstock".format(name)):
                    existing_recipe_name = name
                    feedstock_exists = True
                    break
                else:
                    feedstock_exists = False
            except github.UnknownObjectException:
                feedstock_exists = False

        if feedstock_exists and existing_recipe_name == recipe_name:
            lints.append("Feedstock with the same name exists in conda-forge.")
        elif feedstock_exists:
            hints.append(
                "Feedstock with the name {} exists in conda-forge. Is it the same as this package ({})?".format(
                    existing_recipe_name,
                    recipe_name,
                )
            )

        bio = gh.get_user("bioconda").get_repo("bioconda-recipes")
        try:
            bio.get_dir_contents("recipes/{}".format(recipe_name))
        except github.UnknownObjectException:
            pass
        else:
            hints.append(
                "Recipe with the same name exists in bioconda: "
                "please discuss with @conda-forge/bioconda-recipes."
            )

        url = None
        for source_section in sources_section:
            if str(source_section.get("url")).startswith(
                "https://pypi.io/packages/source/"
            ):
                url = source_section["url"]
        if url:
            # get pypi name from  urls like "https://pypi.io/packages/source/b/build/build-0.4.0.tar.gz"
            pypi_name = url.split("/")[6]
            mapping_request = requests.get(
                "https://raw.githubusercontent.com/regro/cf-graph-countyfair/master/mappings/pypi/name_mapping.yaml"
            )
            if mapping_request.status_code == 200:
                mapping_raw_yaml = mapping_request.content
                mapping = get_yaml().load(mapping_raw_yaml)
                for pkg in mapping:
                    if pkg.get("pypi_name", "") == pypi_name:
                        conda_name = pkg["conda_name"]
                        hints.append(
                            f"A conda package with same name ({conda_name}) already exists."
                        )

    # 2: Check that the recipe maintainers exists:
    for maintainer in maintainers:
        if "/" in maintainer:
            # It's a team. Checking for existence is expensive. Skip for now
            continue
        try:
            gh.get_user(maintainer)
        except github.UnknownObjectException:
            lints.append(
                'Recipe maintainer "{}" does not exist'.format(maintainer)
            )

    # 3: if the recipe dir is inside the example dir
    if recipe_dir is not None and "recipes/example/" in recipe_dir:
        lints.append(
            "Please move the recipe out of the example dir and "
            "into its own dir."
        )

    # 4: Do not delete example recipe
    if is_staged_recipes and recipe_dir is not None:
        recipe_name = "meta.yaml" if not rattler_lint else "recipe.yaml"
        example_meta_fname = os.path.abspath(
            os.path.join(recipe_dir, "..", "example", recipe_name)
        )

        if not os.path.exists(example_meta_fname):
            msg = (
                "Please do not delete the example recipe found in "
                f"`recipes/example/{recipe_name}`."
            )

            if msg not in lints:
                lints.append(msg)

    # 5: Package-specific hints
    # (e.g. do not depend on matplotlib, only matplotlib-base)
    build_reqs = requirements_section.get("build") or []
    host_reqs = requirements_section.get("host") or []
    run_reqs = requirements_section.get("run") or []
    for out in outputs_section:
        _req = out.get("requirements") or {}
        if isinstance(_req, Mapping):
            build_reqs += _req.get("build") or []
            host_reqs += _req.get("host") or []
            run_reqs += _req.get("run") or []
        else:
            run_reqs += _req

    hints_toml_url = "https://raw.githubusercontent.com/conda-forge/conda-forge-pinning-feedstock/main/recipe/linter_hints/hints.toml"
    hints_toml_req = requests.get(hints_toml_url)
    if hints_toml_req.status_code != 200:
        # too bad, but not important enough to throw an error;
        # linter will rerun on the next commit anyway
        return
    hints_toml_str = hints_toml_req.content.decode("utf-8")
    specific_hints = tomllib.loads(hints_toml_str)["hints"]

    for rq in build_reqs + host_reqs + run_reqs:
        dep = rq.split(" ")[0].strip()
        if dep in specific_hints and specific_hints[dep] not in hints:
            hints.append(specific_hints[dep])

    # 6: Check if all listed maintainers have commented:
    pr_number = os.environ.get("STAGED_RECIPES_PR_NUMBER")

    if is_staged_recipes and maintainers and pr_number:
        # Get PR details using GitHub API
        current_pr = gh.get_repo("conda-forge/staged-recipes").get_pull(
            int(pr_number)
        )

        # Get PR author, issue comments, and review comments
        pr_author = current_pr.user.login
        issue_comments = current_pr.get_issue_comments()
        review_comments = current_pr.get_reviews()

        # Combine commenters from both issue comments and review comments
        commenters = {comment.user.login for comment in issue_comments}
        commenters.update({review.user.login for review in review_comments})

        # Check if all maintainers have either commented or are the PR author
        non_participating_maintainers = set()
        for maintainer in maintainers:
            if maintainer not in commenters and maintainer != pr_author:
                non_participating_maintainers.add(maintainer)

        # Add a lint message if there are any non-participating maintainers
        if non_participating_maintainers:
            lints.append(
                f"The following maintainers have not yet confirmed that they are willing to be listed here: "
                f"{', '.join(non_participating_maintainers)}. Please ask them to comment on this PR if they are."
            )

    # 7: Ensure that the recipe has some .ci_support files
    if not is_staged_recipes and recipe_dir is not None:
        ci_support_files = glob(
            os.path.join(recipe_dir, "..", ".ci_support", "*.yaml")
        )
        if not ci_support_files:
            lints.append(
                "The feedstock has no `.ci_support` files and thus will not build any packages."
            )


def is_selector_line(line, allow_platforms=False, allow_keys=set()):
    # Using the same pattern defined in conda-build (metadata.py),
    # we identify selectors.
    line = line.rstrip()
    if line.lstrip().startswith("#"):
        # Don't bother with comment only lines
        return False
    m = sel_pat.match(line)
    if m:
        nouns = {
            w for w in m.group(3).split() if w not in ("not", "and", "or")
        }
        allowed_nouns = (
            {"win", "linux", "osx", "unix"} if allow_platforms else set()
        ) | allow_keys

        if nouns.issubset(allowed_nouns):
            # the selector only contains (a boolean chain of) platform selectors
            # and/or keys from the conda_build_config.yaml
            return False
        else:
            return True
    return False


def is_jinja_line(line):
    line = line.rstrip()
    m = jinja_pat.match(line)
    if m:
        return True
    return False


def selector_lines(lines):
    for i, line in enumerate(lines):
        if is_selector_line(line):
            yield line, i


def jinja_lines(lines):
    for i, line in enumerate(lines):
        if is_jinja_line(line):
            yield line, i


def _format_validation_msg(error: "jsonschema.ValidationError"):
    """Use the data on the validation error to generate improved reporting.

    If available, get the help URL from the first level of the JSON path:

        $(.top_level_key.2nd_level_key)
    """
    help_url = "https://conda-forge.org/docs/maintainer/conda_forge_yml"
    path = error.json_path.split(".")
    descriptionless_schema = {}
    subschema_text = ""

    if error.schema:
        descriptionless_schema = {
            k: v for (k, v) in error.schema.items() if k != "description"
        }

    if len(path) > 1:
        help_url += f"""/#{path[1].split("[")[0].replace("_", "-")}"""
        subschema_text = json.dumps(descriptionless_schema, indent=2)

    return cleandoc(
        f"""
        In conda-forge.yml: [`{error.json_path}`]({help_url}) `=` `{error.instance}`.
{indent(error.message, " " * 12 + "> ")}
            <details>
            <summary>Schema</summary>

            ```json
{indent(subschema_text, " " * 12)}
            ```

            </details>
        """
    )


def main(
    recipe_dir, conda_forge=False, return_hints=False, feedstock_dir=None
):
    recipe_dir = os.path.abspath(recipe_dir)
    build_tool = CONDA_BUILD_TOOL
    if feedstock_dir:
        feedstock_dir = os.path.abspath(feedstock_dir)
        forge_config = _read_forge_config(feedstock_dir)
        if forge_config.get("conda_build_tool", "") == RATTLER_BUILD_TOOL:
            build_tool = RATTLER_BUILD_TOOL

    if build_tool == RATTLER_BUILD_TOOL:
        recipe_file = os.path.join(recipe_dir, "recipe.yaml")
    else:
        recipe_file = os.path.join(recipe_dir, "meta.yaml")

    if not os.path.exists(recipe_file):
        raise IOError(
            f"Feedstock has no recipe/{os.path.basename(recipe_file)}"
        )

    if build_tool == CONDA_BUILD_TOOL:
        with io.open(recipe_file, "rt") as fh:
            content = render_meta_yaml("".join(fh))
            meta = get_yaml().load(content)
    else:
        meta = get_yaml().load(Path(recipe_file))

    results, hints = lintify_recipe(
        meta,
        recipe_dir,
        conda_forge,
        is_rattler_build=build_tool == RATTLER_BUILD_TOOL,
    )
    validation_errors, validation_hints = lintify_forge_yaml(
        recipe_dir=recipe_dir
    )

    results.extend([_format_validation_msg(err) for err in validation_errors])
    hints.extend([_format_validation_msg(hint) for hint in validation_hints])

    if return_hints:
        return results, hints
    else:
        return results


if __name__ == "__main__":
    # This block is supposed to help debug how the rendered version
    # of the linter bot would look like in Github. Taken from
    # https://github.com/conda-forge/conda-forge-webservices/blob/747f75659/conda_forge_webservices/linting.py#L138C1-L146C72
    rel_path = sys.argv[1]
    lints, hints = main(rel_path, False, True)
    messages = []
    if lints:
        all_pass = False
        messages.append(
            "\nFor **{}**:\n\n{}".format(
                rel_path, "\n".join("* {}".format(lint) for lint in lints)
            )
        )
    if hints:
        messages.append(
            "\nFor **{}**:\n\n{}".format(
                rel_path, "\n".join("* {}".format(hint) for hint in hints)
            )
        )

    print(*messages, sep="\n")
