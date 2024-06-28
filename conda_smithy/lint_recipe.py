import copy
import fnmatch
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from glob import glob
from inspect import cleandoc
from textwrap import indent

import github
import jsonschema
import requests
from conda.exceptions import InvalidVersionSpec

if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from conda.models.version import VersionOrder
from conda_build.metadata import (
    FIELDS as _CONDA_BUILD_FIELDS,
)
from conda_build.metadata import (
    ensure_valid_license_family,
)
from ruamel.yaml import CommentedSeq

from conda_smithy.validate_schema import validate_json_schema

from .utils import get_yaml, render_meta_yaml

str_type = str


FIELDS = copy.deepcopy(_CONDA_BUILD_FIELDS)

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


def get_section(parent, name, lints):
    if name == "source":
        return get_list_section(parent, name, lints, allow_single=True)
    elif name == "outputs":
        return get_list_section(parent, name, lints)

    section = parent.get(name, {})
    if not isinstance(section, Mapping):
        lints.append(
            f'The "{name}" section was expected to be a dictionary, but '
            f"got a {type(section).__name__}."
        )
        section = {}
    return section


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


def lint_section_order(major_sections, lints):
    section_order_sorted = sorted(
        major_sections, key=EXPECTED_SECTION_ORDER.index
    )
    if major_sections != section_order_sorted:
        section_order_sorted_str = map(
            lambda s: f"'{s}'", section_order_sorted
        )
        section_order_sorted_str = ", ".join(section_order_sorted_str)
        section_order_sorted_str = "[" + section_order_sorted_str + "]"
        lints.append(
            "The top level meta keys are in an unexpected order. "
            f"Expecting {section_order_sorted_str}."
        )


def lint_about_contents(about_section, lints):
    for about_item in ["home", "license", "summary"]:
        # if the section doesn't exist, or is just empty, lint it.
        if not about_section.get(about_item, ""):
            lints.append(
                f"The {about_item} item is expected in the about section." ""
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
            with open(forge_yaml_filename[0]) as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        forge_yaml = {}

    # This is where we validate against the jsonschema and execute our custom validators.
    return validate_json_schema(forge_yaml)


def lintify_meta_yaml(
    meta, recipe_dir=None, conda_forge=False
) -> (list, list):
    lints = []
    hints = []
    major_sections = list(meta.keys())

    # If the recipe_dir exists (no guarantee within this function) , we can
    # find the meta.yaml within it.
    meta_fname = os.path.join(recipe_dir or "", "meta.yaml")

    sources_section = get_section(meta, "source", lints)
    build_section = get_section(meta, "build", lints)
    requirements_section = get_section(meta, "requirements", lints)
    test_section = get_section(meta, "test", lints)
    about_section = get_section(meta, "about", lints)
    extra_section = get_section(meta, "extra", lints)
    package_section = get_section(meta, "package", lints)
    outputs_section = get_section(meta, "outputs", lints)

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    is_staged_recipes = recipe_dirname != "recipe"

    # 0: Top level keys should be expected
    unexpected_sections = []
    for section in major_sections:
        if section not in EXPECTED_SECTION_ORDER:
            lints.append(f"The top level meta key {section} is unexpected")
            unexpected_sections.append(section)

    for section in unexpected_sections:
        major_sections.remove(section)

    # 1: Top level meta.yaml keys should have a specific order.
    lint_section_order(major_sections, lints)

    # 2: The about section should have a home, license and summary.
    lint_about_contents(about_section, lints)

    # 3a: The recipe should have some maintainers.
    if not extra_section.get("recipe-maintainers", []):
        lints.append(
            "The recipe could do with some maintainers listed in "
            "the `extra/recipe-maintainers` section."
        )

    # 3b: Maintainers should be a list
    if not (
        isinstance(extra_section.get("recipe-maintainers", []), Sequence)
        and not isinstance(
            extra_section.get("recipe-maintainers", []), str_type
        )
    ):
        lints.append("Recipe maintainers should be a json list.")

    # 4: The recipe should have some tests.
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

    # 5: License cannot be 'unknown.'
    license = about_section.get("license", "").lower()
    if "unknown" == license.strip():
        lints.append("The recipe license cannot be unknown.")

    # 6: Selectors should be in a tidy form.
    if recipe_dir is not None and os.path.exists(meta_fname):
        bad_selectors, bad_lines = [], []
        # pyXY selectors for python version X.Y
        python_selectors_lint, python_lines_lint = [], []
        python_selectors_hint, python_lines_hint = [], []
        # Good selectors look like ".*\s\s#\s[...]"
        good_selectors_pat = re.compile(r"(.+?)\s{2,}#\s\[(.+)\](?(2).*)$")
        # Look out for py27, py35 selectors; we prefer py==35
        python_selectors_pat = re.compile(r".+#\s*\[.*?(py\d{2,3}).*\]")
        with open(meta_fname) as fh:
            for selector_line, line_number in selector_lines(fh):
                if not good_selectors_pat.match(selector_line):
                    bad_selectors.append(selector_line)
                    bad_lines.append(line_number)
                python_matches = python_selectors_pat.match(selector_line)
                if python_matches:
                    for py_match in python_matches.groups():
                        if int(py_match[2:]) in (27, 34, 35, 36):
                            # py27, py35 and so on are ok up to py36 (included); only warn
                            python_selectors_hint.append(selector_line)
                            python_lines_hint.append(line_number)
                        else:
                            python_selectors_lint.append(selector_line)
                            python_lines_lint.append(line_number)
        if bad_selectors:
            lints.append(
                "Selectors are suggested to take a "
                "``<two spaces>#<one space>[<expression>]`` form."
                f" See lines {bad_lines}"
            )
        if python_selectors_hint:
            hints.append(
                "Old-style Python selectors (py27, py34, py35, py36) are "
                "deprecated. Instead, consider using the int ``py``. For "
                f"example: ``# [py>=36]``. See lines {python_lines_hint}"
            )
        if python_selectors_lint:
            lints.append(
                "Old-style Python selectors (py27, py35, etc) are only available "
                "for Python 2.7, 3.4, 3.5, and 3.6. Please use explicit comparisons "
                "with the integer ``py``, e.g. ``# [py==37]`` or ``# [py>=37]``. "
                f"See lines {python_lines_lint}"
            )

    # 7: The build section should have a build number.
    if build_section.get("number", None) is None:
        lints.append("The recipe must have a `build/number` section.")

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
    for source_section in sources_section:
        if "url" in source_section and not (
            {"sha1", "sha256", "md5"} & set(source_section.keys())
        ):
            lints.append(
                "When defining a source/url please add a sha256, sha1 "
                "or md5 checksum (sha256 preferably)."
            )

    # 10: License should not include the word 'license'.
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

    # 11: There should be one empty line at the end of the file.
    if recipe_dir is not None and os.path.exists(meta_fname):
        with open(meta_fname) as f:
            lines = f.read().split("\n")
        # Count the number of empty lines from the end of the file
        empty_lines = itertools.takewhile(lambda x: x == "", reversed(lines))
        end_empty_lines_count = len(list(empty_lines))
        if end_empty_lines_count > 1:
            lints.append(
                f"There are {end_empty_lines_count - 1} too many lines.  "
                "There should be one empty line at the end of the "
                "file."
            )
        elif end_empty_lines_count < 1:
            lints.append(
                "There are too few lines.  There should be one empty "
                "line at the end of the file."
            )

    # 12: License family must be valid (conda-build checks for that)
    try:
        ensure_valid_license_family(meta)
    except RuntimeError as e:
        lints.append(str(e))

    # 12a: License family must be valid (conda-build checks for that)
    license_family = about_section.get("license_family", license).lower()
    license_file = about_section.get("license_file", None)
    if not license_file and any(
        f for f in NEEDED_FAMILIES if f in license_family
    ):
        lints.append("license_file entry is missing, but is required.")

    # 13: Check that the recipe name is valid
    recipe_name = package_section.get("name", "").strip()
    if re.match(r"^[a-z0-9_\-.]+$", recipe_name) is None:
        lints.append(
            "Recipe name has invalid characters. only lowercase alpha, numeric, "
            "underscores, hyphens and dots allowed"
        )

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
                    f"The {section} section contained an unexpected "
                    f"subsection name. {subsection} is not a valid subsection"
                    " name."
                )
            elif section == "source" or section == "outputs":
                for source_subsection in subsection:
                    if source_subsection not in expected_subsections:
                        lints.append(
                            f"The {section} section contained an unexpected "
                            f"subsection name. {source_subsection} is not a valid subsection"
                            " name."
                        )
    # 17: Validate noarch
    noarch_value = build_section.get("noarch")
    if noarch_value is not None:
        valid_noarch_values = ["python", "generic"]
        if noarch_value not in valid_noarch_values:
            valid_noarch_str = "`, `".join(valid_noarch_values)
            lints.append(
                f"Invalid `noarch` value `{noarch_value}`. Should be one of `{valid_noarch_str}`."
            )

    conda_build_config_filename = None
    if recipe_dir:
        conda_build_config_filename = find_local_config_file(
            recipe_dir, "conda_build_config.yaml"
        )

        if conda_build_config_filename:
            with open(conda_build_config_filename) as fh:
                conda_build_config_keys = set(get_yaml().load(fh).keys())
        else:
            conda_build_config_keys = set()

        forge_yaml_filename = find_local_config_file(
            recipe_dir, "conda-forge.yml"
        )

        if forge_yaml_filename:
            with open(forge_yaml_filename) as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        conda_build_config_keys = set()
        forge_yaml = {}

    # 18: noarch doesn't work with selectors for runtime dependencies
    if noarch_value is not None and os.path.exists(meta_fname):
        noarch_platforms = len(forge_yaml.get("noarch_platforms", [])) > 1
        with open(meta_fname) as fh:
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
                        f"`noarch: {noarch_value}`."
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
                            f"`noarch: {noarch_value}`."
                        )
                        break

    # 19: check version
    version = package_section.get("version")
    if not version:
        lints.append("Package version is missing.")
    else:
        try:
            VersionOrder(str(version))
        except InvalidVersionSpec as e:
            lints.append(
                f"Package version {version} doesn't match conda spec: {e}"
            )

    # 20: Jinja2 variable definitions should be nice.
    if recipe_dir is not None and os.path.exists(meta_fname):
        bad_jinja = []
        bad_lines = []
        # Good Jinja2 variable definitions look like "{% set .+ = .+ %}"
        good_jinja_pat = re.compile(r"\s*\{%\s(set)\s[^\s]+\s=\s[^\s]+\s%\}")
        with open(meta_fname) as fh:
            for jinja_line, line_number in jinja_lines(fh):
                if not good_jinja_pat.match(jinja_line):
                    bad_jinja.append(jinja_line)
                    bad_lines.append(line_number)
        if bad_jinja:
            lints.append(
                "Jinja2 variable definitions are suggested to "
                "take a ``{%<one space>set<one space>"
                "<variable name><one space>=<one space>"
                "<expression><one space>%}`` form. See lines "
                f"{bad_lines}"
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
            req, _, _ = requirement.partition("#")
            if "{{" in req:
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
                    f"If {str(language)} is a host requirement, it should be a run requirement."
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
                            f"Non noarch packages should have {str(language)} requirement without any version constraints."
                        )

    # 24: jinja2 variable references should be {{<one space>var<one space>}}
    if recipe_dir is not None and os.path.exists(meta_fname):
        bad_vars = []
        bad_lines = []
        with open(meta_fname) as fh:
            for i, line in enumerate(fh.readlines()):
                for m in JINJA_VAR_PAT.finditer(line):
                    if m.group(1) is not None:
                        var = m.group(1)
                        if var != f" {var.strip()} ":
                            bad_vars.append(m.group(1).strip())
                            bad_lines.append(i + 1)
        if bad_vars:
            hints.append(
                "Jinja2 variable references are suggested to "
                "take a ``{{<one space><variable name><one space>}}``"
                f" form. See lines {bad_lines}."
            )

    # 25: require a lower bound on python version
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
        for pin in fnmatch.filter(pinning_section, "compatible_pin*"):
            if pin.split()[1] in subpackage_names:
                lints.append(
                    "pin_subpackage should be used instead of"
                    f" pin_compatible for `{pin.split()[1]}`"
                    " because it is one of the known outputs of this recipe:"
                    f" {subpackage_names}."
                )
        for pin in fnmatch.filter(pinning_section, "subpackage_pin*"):
            if pin.split()[1] not in subpackage_names:
                lints.append(
                    "pin_compatible should be used instead of"
                    f" pin_subpackage for `{pin.split()[1]}`"
                    " because it is not a known output of this recipe:"
                    f" {subpackage_names}."
                )

    def check_pins_build_and_requirements(top_level):
        if "build" in top_level and "run_exports" in top_level["build"]:
            check_pins(top_level["build"]["run_exports"])
        if "requirements" in top_level and "run" in top_level["requirements"]:
            check_pins(top_level["requirements"]["run"])
        if "requirements" in top_level and "host" in top_level["requirements"]:
            check_pins(top_level["requirements"]["host"])

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
        with open(meta_fname) as f:
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
    if build_reqs and ("{{ compiler('rust') }}" in build_reqs):
        if "cargo-bundle-licenses" not in build_reqs:
            lints.append(
                "Rust packages must include the licenses of the Rust dependencies. "
                "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust"
            )

    # 29: Check that go licenses are bundled.
    if build_reqs and ("{{ compiler('go') }}" in build_reqs):
        if "go-licenses" not in build_reqs:
            lints.append(
                "Go packages must include the licenses of the Go dependencies. "
                "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go"
            )

    # hints
    # 1: suggest pip
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

    # 2: suggest python noarch (skip on feedstocks)
    if (
        noarch_value is None
        and build_reqs
        and not any(["_compiler_stub" in b for b in build_reqs])
        and ("pip" in build_reqs)
        and (is_staged_recipes or not conda_forge)
    ):
        with open(meta_fname) as fh:
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
    shellcheck_enabled = False
    shell_scripts = []
    if recipe_dir:
        shell_scripts = glob(os.path.join(recipe_dir, "*.sh"))
        forge_yaml = find_local_config_file(recipe_dir, "conda-forge.yml")
        if shell_scripts and forge_yaml:
            with open(forge_yaml) as fh:
                code = get_yaml().load(fh)
                shellcheck_enabled = code.get("shellcheck", {}).get(
                    "enabled", shellcheck_enabled
                )

    if shellcheck_enabled and shutil.which("shellcheck") and shell_scripts:
        max_shellcheck_lines = 50
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
            if len(findings) > max_shellcheck_lines:
                hints.append(
                    "Output restricted, there are '%s' more lines."
                    % (len(findings) - max_shellcheck_lines)
                )
        elif p.returncode != 0:
            # Something went wrong.
            hints.append(
                "There have been errors while scanning with shellcheck."
            )

    # 4: Check for SPDX
    import license_expression

    license = about_section.get("license", "")
    licensing = license_expression.Licensing()
    parsed_exceptions = []
    try:
        parsed_licenses = []
        parsed_licenses_with_exception = licensing.license_symbols(
            license.strip(), decompose=False
        )
        for li in parsed_licenses_with_exception:
            if isinstance(li, license_expression.LicenseWithExceptionSymbol):
                parsed_licenses.append(li.license_symbol.key)
                parsed_exceptions.append(li.exception_symbol.key)
            else:
                parsed_licenses.append(li.key)
    except license_expression.ExpressionError:
        parsed_licenses = [license]

    licenseref_regex = re.compile(r"^LicenseRef[a-zA-Z0-9\-.]*$")
    filtered_licenses = []
    for license in parsed_licenses:
        if not licenseref_regex.match(license):
            filtered_licenses.append(license)

    with open(os.path.join(os.path.dirname(__file__), "licenses.txt")) as f:
        expected_licenses = f.readlines()
        expected_licenses = set([li.strip() for li in expected_licenses])
    with open(
        os.path.join(os.path.dirname(__file__), "license_exceptions.txt")
    ) as f:
        expected_exceptions = f.readlines()
        expected_exceptions = set([li.strip() for li in expected_exceptions])
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

    # 5: stdlib-related hints
    global_build_reqs = requirements_section.get("build") or []
    global_run_reqs = requirements_section.get("run") or []
    global_constraints = requirements_section.get("run_constrained") or []

    stdlib_hint = (
        "This recipe is using a compiler, which now requires adding a build "
        'dependence on `{{ stdlib("c") }}` as well. Note that this rule applies to '
        "each output of the recipe using a compiler. For further details, please "
        "see https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    pat_compiler_stub = re.compile(
        "(m2w64_)?(c|cxx|fortran|rust)_compiler_stub"
    )
    outputs = get_section(meta, "outputs", lints)
    output_reqs = [x.get("requirements", {}) for x in outputs]

    # deal with cb2 recipes (no build/host/run distinction)
    output_reqs = [
        {"host": x, "run": x} if isinstance(x, CommentedSeq) else x
        for x in output_reqs
    ]

    # collect output requirements
    output_build_reqs = [x.get("build", []) or [] for x in output_reqs]
    output_run_reqs = [x.get("run", []) or [] for x in output_reqs]
    output_contraints = [
        x.get("run_constrained", []) or [] for x in output_reqs
    ]

    # aggregate as necessary
    all_build_reqs = [global_build_reqs] + output_build_reqs
    all_build_reqs_flat = global_build_reqs
    all_run_reqs_flat = global_run_reqs
    all_contraints_flat = global_constraints
    [all_build_reqs_flat := all_build_reqs_flat + x for x in output_build_reqs]
    [all_run_reqs_flat := all_run_reqs_flat + x for x in output_run_reqs]
    [all_contraints_flat := all_contraints_flat + x for x in output_contraints]

    # this check needs to be done per output --> use separate (unflattened) requirements
    for build_reqs in all_build_reqs:
        has_compiler = any(pat_compiler_stub.match(rq) for rq in build_reqs)
        if has_compiler and "c_stdlib_stub" not in build_reqs:
            if stdlib_hint not in hints:
                hints.append(stdlib_hint)

    sysroot_hint = (
        "You're setting a requirement on sysroot_linux-<arch> directly; this should "
        'now be done by adding a build dependence on `{{ stdlib("c") }}`, and '
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
        'should now be done by adding a build dependence on `{{ stdlib("c") }}`, '
        "and overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for "
        "the respective platform as necessary. For further details, please see "
        "https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    to_check = all_run_reqs_flat + all_contraints_flat
    if any(req.startswith("__osx >") for req in to_check):
        if osx_hint not in hints:
            hints.append(osx_hint)

    # stdlib issues in CBC
    cbc_lines = []
    if conda_build_config_filename:
        with open(conda_build_config_filename) as fh:
            cbc_lines = fh.readlines()

    # filter on osx-relevant lines
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


def run_conda_forge_specific(meta, recipe_dir, lints, hints):
    gh = github.Github(os.environ["GH_TOKEN"])

    # Retrieve sections from meta
    package_section = get_section(meta, "package", lints)
    extra_section = get_section(meta, "extra", lints)
    sources_section = get_section(meta, "source", lints)
    requirements_section = get_section(meta, "requirements", lints)
    outputs_section = get_section(meta, "outputs", lints)

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
                if cf.get_repo(f"{name}-feedstock"):
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
                f"Feedstock with the name {existing_recipe_name} exists in conda-forge. Is it the same as this package ({recipe_name})?"
            )

        bio = gh.get_user("bioconda").get_repo("bioconda-recipes")
        try:
            bio.get_dir_contents(f"recipes/{recipe_name}")
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
            lints.append(f'Recipe maintainer "{maintainer}" does not exist')

    # 3: if the recipe dir is inside the example dir
    if recipe_dir is not None and "recipes/example/" in recipe_dir:
        lints.append(
            "Please move the recipe out of the example dir and "
            "into its own dir."
        )

    # 4: Do not delete example recipe
    if is_staged_recipes and recipe_dir is not None:
        example_meta_fname = os.path.abspath(
            os.path.join(recipe_dir, "..", "example", "meta.yaml")
        )

        if not os.path.exists(example_meta_fname):
            msg = (
                "Please do not delete the example recipe found in "
                "`recipes/example/meta.yaml`."
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


def _format_validation_msg(error: jsonschema.ValidationError):
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


def main(recipe_dir, conda_forge=False, return_hints=False):
    recipe_dir = os.path.abspath(recipe_dir)
    recipe_meta = os.path.join(recipe_dir, "meta.yaml")
    if not os.path.exists(recipe_dir):
        raise OSError("Feedstock has no recipe/meta.yaml.")

    with open(recipe_meta) as fh:
        content = render_meta_yaml("".join(fh))
        meta = get_yaml().load(content)

    results, hints = lintify_meta_yaml(meta, recipe_dir, conda_forge)
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
                rel_path, "\n".join(f"* {lint}" for lint in lints)
            )
        )
    if hints:
        messages.append(
            "\nFor **{}**:\n\n{}".format(
                rel_path, "\n".join(f"* {hint}" for hint in hints)
            )
        )

    print(*messages, sep="\n")
