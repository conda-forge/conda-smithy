import inspect
import unittest
from typing import Set, Callable

from conda_smithy import lint_forge_yml
from conda_smithy.lint_forge_yml import lint_extra_fields
from conda_smithy.linting_types import LintsHints


class TestHintExtraFields(unittest.TestCase):
    def test_extra_build_platforms_platform(self):
        forge_yml = {
            "build_platform": {
                "osx_64": "linux_64",
                "UNKNOWN_PLATFORM": "linux_64",
            }
        }

        ret = lint_extra_fields(forge_yml)

        self.assertEquals(len(ret.lints), 0)
        self.assertEquals(len(ret.hints), 1)

        self.assertIn(
            "Unexpected key build_platform.UNKNOWN_PLATFORM", ret.hints[0]
        )

    def test_extra_os_version_platform(self):
        forge_yml = {
            "os_version": {
                "UNKNOWN_PLATFORM_2": "10.9",
            }
        }

        ret = lint_extra_fields(forge_yml)

        self.assertEquals(len(ret.lints), 0)
        self.assertEquals(len(ret.hints), 1)

        self.assertIn(
            "Unexpected key os_version.UNKNOWN_PLATFORM_2", ret.hints[0]
        )

    def test_extra_provider_platform(self):
        forge_yml = {
            "provider": {
                "osx_64": "travis",
                "UNKNOWN_PLATFORM_3": "azure",
            }
        }

        ret = lint_extra_fields(forge_yml)

        self.assertEquals(len(ret.lints), 0)
        self.assertEquals(len(ret.hints), 1)

        self.assertIn(
            "Unexpected key provider.UNKNOWN_PLATFORM_3", ret.hints[0]
        )


def test_complete_linter_list():
    module_linters: Set[Callable[..., LintsHints]] = set()

    for name, member in inspect.getmembers(lint_forge_yml):
        if (
            inspect.isfunction(member)
            and inspect.signature(member).return_annotation == LintsHints
        ):
            assert name.startswith(
                "lint_"
            ), f"{name} does not start with lint_ but returns LintsHints"
            module_linters.add(member)
            continue

        assert not name.startswith(
            "lint_"
        ), f"{name} starts with lint_ but does not return LintsHints"

    assert module_linters == set(
        lint_forge_yml.FORGE_YAML_LINTERS
    ), "FORGE_YAML_LINTERS is incomplete."
