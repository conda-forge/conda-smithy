import os
import re


import sys
from typing import Dict, List, Mapping

import github
import requests

from rattler_build_conda_compat.loader import load_yaml
from conda.models.version import VersionOrder

if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib

REQUIREMENTS_ORDER = ["build", "host", "run"]
EXPECTED_SINGLE_OUTPUT_SECTION_ORDER = [
    "context",
    "package",
    "source",
    "build",
    "requirements",
    "tests",
    "about",
    "extra",
]

EXPECTED_MUTIPLE_OUTPUT_SECTION_ORDER = [
    "context",
    "recipe",
    "source",
    "build",
    "outputs",
    "about",
    "extra",
]


JINJA_VAR_PAT = re.compile(r"\${{(.*?)}}")


def _is_keys_in_order(input_keys, expected_order):
    # Filter the keys of the input dictionary based on the expected order
    filtered_keys = [key for key in expected_order if key in input_keys]

    # Check if the filtered keys are in the same order as they appear in the actual keys
    index = 0
    for key in filtered_keys:
        try:
            index = input_keys.index(key, index)
        except ValueError:
            return False
        index += 1

    return True


def lint_section_order(major_sections, lints):
    expected_section = (
        EXPECTED_MUTIPLE_OUTPUT_SECTION_ORDER
        if "outputs" in major_sections
        else EXPECTED_SINGLE_OUTPUT_SECTION_ORDER
    )

    in_order = _is_keys_in_order(major_sections, expected_section)

    if not in_order:
        section_order_sorted_str = map(lambda s: "'%s'" % s, expected_section)
        section_order_sorted_str = ", ".join(section_order_sorted_str)
        section_order_sorted_str = "[" + section_order_sorted_str + "]"
        lints.append(
            "The top level meta keys are in an unexpected order. "
            "Expecting {}.".format(section_order_sorted_str)
        )


def lint_about_contents(about_section, lints):
    for about_item in ["homepage", "license", "summary"]:
        # if the section doesn't exist, or is just empty, lint it.
        if not about_section.get(about_item, ""):
            lints.append(
                "The {} item is expected in the about section."
                "".format(about_item)
            )


def lint_recipe_tests(test_section=dict(), outputs_section=list()):
    TEST_KEYS = {"script", "python"}
    lints = []
    hints = []

    if not any(key in TEST_KEYS for key in test_section):
        if not outputs_section:
            lints.append("The recipe must have some tests.")
        else:
            has_outputs_test = False
            no_test_hints = []
            for section in outputs_section:
                test_section = section.get("tests", {})
                if any(key in TEST_KEYS for key in test_section):
                    has_outputs_test = True
                else:
                    no_test_hints.append(
                        "It looks like the '{}' output doesn't "
                        "have any tests.".format(section.get("name", "???"))
                    )
            if has_outputs_test:
                hints.extend(no_test_hints)
            else:
                lints.append("The recipe must have some tests.")

    return lints, hints


def lint_requirements_order(requirements_section: Dict, lints: List):
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


def lint_has_recipe_file(about_section, lints):
    license_file = about_section.get("license_file", None)
    if not license_file:
        lints.append("license_file entry is missing, but is required.")


def lint_package_name(package_section: Dict, context_section: Dict):
    package_name = str(package_section.get("name"))
    context_name = str(context_section.get("name"))
    actual_name = (
        package_name
        if package_name is not None and not package_name.startswith("$")
        else context_name
    )

    actual_name = actual_name.strip()
    if re.match(r"^[a-z0-9_\-.]+$", actual_name) is None:
        return """Recipe name has invalid characters. only lowercase alpha, numeric, underscores, hyphens and dots allowed"""


def lint_legacy_patterns(requirements_section):
    lints = []
    build_reqs = requirements_section.get("build", None)
    if build_reqs and ("numpy x.x" in build_reqs):
        lints.append(
            "Using pinned numpy packages is a deprecated pattern.  Consider "
            "using the method outlined "
            "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy)."
        )
    return lints


def lint_usage_of_selectors_for_noarch(
    noarch_value, build_section, requirements_section
):
    lints = []
    for section in requirements_section:
        section_requirements = requirements_section[section]

        if not section_requirements:
            continue

        if any(isinstance(req, dict) for req in section_requirements):
            lints.append(
                "`noarch` packages can't have skips with selectors. If "
                "the selectors are necessary, please remove "
                "`noarch: {}`.".format(noarch_value)
            )
            break

    if "skip" in build_section:
        lints.append(
            "`noarch` packages can't have skips with selectors. If "
            "the selectors are necessary, please remove "
            "`noarch: {}`.".format(noarch_value)
        )

    return lints


def lint_package_version(package_section: dict, context_section: dict):
    package_ver = str(package_section.get("version"))
    context_ver = str(context_section.get("version"))
    ver = (
        package_ver
        if package_ver is not None and not package_ver.startswith("$")
        else context_ver
    )

    try:
        VersionOrder(ver)

    except Exception:
        return "Package version {} doesn't match conda spec".format(ver)


def lint_legacy_compilers(build_reqs):
    if build_reqs and ("toolchain" in build_reqs):
        return """Using toolchain directly in this manner is deprecated. Consider
            using the compilers outlined
            [here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers)."""


def lint_usage_of_single_space_in_pinned_requirements(
    requirements_section: dict,
):
    def verify_requirement(requirement, section):
        lints = []
        if "${{" in requirement:
            return lints
        parts = requirement.split()
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
            return lints
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

        return lints

    lints = []
    for section, requirements in requirements_section.items():
        if not requirements:
            continue
        for req in requirements:
            lints.extend(verify_requirement(req, section))
    return lints


def lint_non_noarch_dont_constrain_python_and_rbase(requirements_section):
    check_languages = ["python", "r-base"]
    host_reqs = requirements_section.get("host") or []
    run_reqs = requirements_section.get("run") or []

    lints = []

    for language in check_languages:
        filtered_host_reqs = [
            req for req in host_reqs if req.startswith(f"{language}")
        ]
        filtered_run_reqs = [
            req for req in run_reqs if req.startswith(f"{language}")
        ]

        if filtered_host_reqs and not filtered_run_reqs:
            lints.append(
                f"If {language} is a host requirement, it should be a run requirement."
            )

        for reqs in [filtered_host_reqs, filtered_run_reqs]:
            if language not in reqs:
                for req in reqs:
                    splitted = req.split(" ", 1)
                    if len(splitted) > 1:
                        constraint = req.split(" ", 1)[1]
                        if constraint.startswith(">") or constraint.startswith(
                            "<"
                        ):
                            lints.append(
                                f"Non noarch packages should have {language} requirement without any version constraints."
                            )

    return lints


def lint_variable_reference_should_have_space(recipe_dir, recipe_file):
    hints = []
    if recipe_dir is not None and os.path.exists(recipe_file):
        bad_vars = []
        bad_lines = []
        with open(recipe_file, "r") as fh:
            for i, line in enumerate(fh.readlines()):
                for m in JINJA_VAR_PAT.finditer(line):
                    if m.group(1) is not None:
                        var = m.group(1)
                        if var != " %s " % var.strip():
                            bad_vars.append(m.group(1).strip())
                            bad_lines.append(i + 1)
        if bad_vars:
            hints.append(
                "Jinja2 variable references are suggested to "
                "take a ``${{<one space><variable name><one space>}}``"
                " form. See lines %s." % (bad_lines,)
            )

    return hints


def lint_lower_bound_on_python(run_requirements, outputs_section):
    lints = []
    # if noarch_value == "python" and not outputs_section:
    for req in run_requirements:
        if (req.strip().split()[0] == "python") and (req != "python"):
            break
    else:
        lints.append(
            "noarch: python recipes are required to have a lower bound "
            "on the python version. Typically this means putting "
            "`python >=3.6` in **both** `host` and `run` but you should check "
            "upstream for the package's Python compatibility."
        )


def hint_pip_usage(build_section):
    hints = []

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
    return hints


def hint_noarch_usage(build_section, requirement_section: dict):
    build_reqs = requirement_section.get("build", None)
    hints = []
    if (
        build_reqs
        and not any(
            [
                b.startswith("${{")
                and ("compiler('c')" in b or 'compiler("c")' in b)
                for b in build_reqs
            ]
        )
        and ("pip" in build_reqs)
    ):
        no_arch_possible = True
        if "skip" in build_section:
            no_arch_possible = False

        for _, section_requirements in requirement_section.items():
            if any(
                isinstance(requirement, dict)
                for requirement in section_requirements
            ):
                no_arch_possible = False
                break

        if no_arch_possible:
            hints.append(
                "Whenever possible python packages should use noarch. "
                "See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds"
            )

    return hints
