"""Unit tests for staging-output handling in the v1 recipe linter.

Staging outputs produce no artifact and have a restricted schema (no
`tests:`, no `run:` requirements), so the linter must skip them when
checking per-output tests.
"""

from __future__ import annotations

from conda_smithy.linter.conda_recipe_v1_linter import lint_recipe_tests


def test_lint_recipe_tests_skips_staging_outputs() -> None:
    """A recipe with one staging + one package output (both with tests on the
    package side) must not produce a lint or a hint for the staging entry.
    """
    outputs = [
        {"staging": {"name": "libfoo-build"}},
        {
            "package": {"name": "libfoo"},
            "name": "libfoo",
            "tests": [{"script": ["test -f $PREFIX/lib/libfoo.so"]}],
        },
    ]
    lints: list[str] = []
    hints: list[str] = []
    lint_recipe_tests(
        recipe_dir=None,
        test_section=[],
        outputs_section=outputs,
        lints=lints,
        hints=hints,
    )
    assert lints == []
    assert hints == []


def test_lint_recipe_tests_still_flags_missing_tests_on_package_outputs() -> None:
    """Regression: a real package output without tests must still produce a hint.
    The staging entry must not contribute a second '???' hint.

    On trunk (without the staging skip), this produces two hints:
      - "'???' output doesn't have any tests" (from the staging entry)
      - "'libfoo' output doesn't have any tests"
    With the fix: only the 'libfoo' hint.
    """
    outputs = [
        {"staging": {"name": "libfoo-build"}},
        {"name": "libfoo"},  # no tests
        {"name": "libfoo-dev", "tests": [{"script": ["true"]}]},
    ]
    lints: list[str] = []
    hints: list[str] = []
    lint_recipe_tests(
        recipe_dir=None,
        test_section=[],
        outputs_section=outputs,
        lints=lints,
        hints=hints,
    )
    assert len(hints) == 1
    assert "'libfoo'" in hints[0]
