import os
from typing import Any, Dict, List, Optional

from rattler_build_conda_compat.jinja.jinja import (
    RecipeWithContext,
    render_recipe_with_context,
)

from conda_smithy.linter.errors import HINT_NO_ARCH
from conda_smithy.linter.utils import (
    TEST_FILES,
    _lint_package_version,
    _lint_recipe_name,
)

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

EXPECTED_MULTIPLE_OUTPUT_SECTION_ORDER = [
    "context",
    "recipe",
    "source",
    "build",
    "outputs",
    "about",
    "extra",
]
TEST_KEYS = {"script", "python"}


def lint_recipe_tests(
    recipe_dir: Optional[str],
    test_section: List[Dict[str, Any]],
    outputs_section: List[Dict[str, Any]],
    lints: List[str],
    hints: List[str],
):
    tests_lints = []
    tests_hints = []

    if not any(key in TEST_KEYS for key in test_section):
        a_test_file_exists = recipe_dir is not None and any(
            os.path.exists(os.path.join(recipe_dir, test_file))
            for test_file in TEST_FILES
        )
        if a_test_file_exists:
            return

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
            hints.append(HINT_NO_ARCH)


def lint_recipe_name(
    recipe_content: RecipeWithContext,
    lints: List[str],
) -> None:
    rendered_context_recipe = render_recipe_with_context(recipe_content)
    package_name = (
        rendered_context_recipe.get("package", {}).get("name", "").strip()
    )
    recipe_name = (
        rendered_context_recipe.get("recipe", {}).get("name", "").strip()
    )
    name = package_name or recipe_name

    lint_msg = _lint_recipe_name(name)
    if lint_msg:
        lints.append(lint_msg)


def lint_package_version(
    recipe_content: RecipeWithContext,
    lints: List[str],
) -> None:
    rendered_context_recipe = render_recipe_with_context(recipe_content)
    package_version = (
        rendered_context_recipe.get("package", {}).get("version", "").strip()
    )
    recipe_version = (
        rendered_context_recipe.get("recipe", {}).get("version", "").strip()
    )
    version = package_version or recipe_version

    lint_msg = _lint_package_version(version)

    if lint_msg:
        lints.append(lint_msg)


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
                f"`noarch: {noarch_value}`."
            )
            break

    if "skip" in build_section:
        lints.append(
            "`noarch` packages can't have skips with selectors. If "
            "the selectors are necessary, please remove "
            f"`noarch: {noarch_value}`."
        )
