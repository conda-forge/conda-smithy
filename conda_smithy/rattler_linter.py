import re


import sys
from typing import Any, Dict, List


from conda.models.version import VersionOrder

if sys.version_info[:2] < (3, 11):
    pass
else:
    pass

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


def lint_recipe_tests(
    test_section: Dict[str, Any],
    outputs_section: Dict[str, Any],
    lints: List[str],
    hints: List[str],
):
    TEST_KEYS = {"script", "python"}
    tests_lints = []
    tests_hints = []

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

    lints.extend(tests_lints)
    hints.extend(tests_hints)


def lint_package_name(
    package_section: Dict[str, Any],
    context_section: Dict[str, Any],
    lints: List[str],
):
    package_name = str(package_section.get("name"))
    context_name = str(context_section.get("name"))
    actual_name = (
        package_name
        if package_name is not None and not package_name.startswith("$")
        else context_name
    )

    actual_name = actual_name.strip()
    if re.match(r"^[a-z0-9_\-.]+$", actual_name) is None:
        lints.append(
            """Recipe name has invalid characters. only lowercase alpha, numeric, underscores, hyphens and dots allowed"""
        )


def lint_usage_of_selectors_for_noarch(
    noarch_value: str,
    build_section: Dict[str, Any],
    requirements_section: Dict[str, Any],
    lints: List[str],
):
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


def lint_package_version(
    package_section: Dict[str, Any],
    context_section: Dict[str, Any],
    lints: List[str],
):
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
        lints.append(f"Package version {ver} doesn't match conda spec")


def hint_noarch_usage(
    build_section: Dict[str, Any],
    requirement_section: Dict[str, Any],
    hints: List[str],
):
    build_reqs = requirement_section.get("build", None)
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
