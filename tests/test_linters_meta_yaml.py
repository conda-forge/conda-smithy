import inspect
import unittest
from pathlib import Path
from typing import Set, Callable

from conda_smithy import linters_meta_yaml
from conda_smithy.linters_meta_yaml import MetaYamlLintExtras
from conda_smithy.linting_utils import LintsHints


class TestLintersMetaYaml(unittest.TestCase):
    def test_lint_recipe_dir_inside_example_dir_no_recipe_dir(self):
        results = linters_meta_yaml.lint_recipe_dir_inside_example_dir(
            {}, MetaYamlLintExtras(is_conda_forge=True)
        )

        self.assertEqual(results, LintsHints())

    def test_lint_recipe_dir_inside_example_dir(self):
        recipe_dir = Path("recipes") / "example"

        results = linters_meta_yaml.lint_recipe_dir_inside_example_dir(
            {}, MetaYamlLintExtras(recipe_dir, is_conda_forge=True)
        )

        message = "Please move the recipe out of the example dir and into its own dir."

        self.assertIn(message, results.lints)


def test_complete_linter_list():
    module_linters: Set[Callable[..., LintsHints]] = set()

    for name, member in inspect.getmembers(linters_meta_yaml):
        if not inspect.isfunction(member):
            continue
        if inspect.signature(member).return_annotation == LintsHints:
            assert name.startswith(
                ("lint_", "_helper_")
            ), f"{name} does not start with lint_ or _helper_ but returns LintsHints"

            if name.startswith("lint_"):
                module_linters.add(member)
            continue

        assert not name.startswith(
            "lint_"
        ), f"{name} starts with lint_ but does not return LintsHints"

    assert module_linters == set(
        linters_meta_yaml.META_YAML_LINTERS
    ), "META_YAML_LINTERS is incomplete."
