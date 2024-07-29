import re
from typing import Any, Dict, List

from conda_smithy.linter.errors import HINT_NO_ARCH

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


def lint_package_name(
    package_section: Dict[str, Any],
    context_section: Dict[str, Any],
    lints: List[str],
) -> None:
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
