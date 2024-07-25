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
