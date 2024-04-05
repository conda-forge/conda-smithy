import inspect
from typing import Set, Callable

from conda_smithy import linters_meta_yaml
from conda_smithy.linting_utils import LintsHints


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
