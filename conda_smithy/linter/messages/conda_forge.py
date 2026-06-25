"""
Messages exclusive to conda-forge recipes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from conda_smithy.linter.messages.base import LinterMessage

if TYPE_CHECKING:
    from typing import Self

CATEGORIES = {
    "CF": "conda-forge specific rules",
}


@dataclass(kw_only=True)
class MaintainerMissing(LinterMessage):
    """
    Maintainers listed in `extra.recipe-maintainers` must be valid Github usernames
    or `@conda-forge/*` teams.
    """

    kind = "lint"
    identifier = "CF-001"
    message = 'Recipe maintainer ${team_or}"${maintainer}" does not exist'
    maintainer: str
    path: str = "recipe/(meta|recipe).yaml"

    def _render_attributes(self):
        return {
            "maintainer": self.maintainer,
            "team_or": "team " if "/" in self.maintainer else "",
        }

    @classmethod
    def examples(cls) -> list[Self]:
        return [
            cls(maintainer="@banned-user"),
            cls(maintainer="@conda-forge/deleted-team"),
        ]


@dataclass(kw_only=True)
class PackageToAvoid(LinterMessage):
    """
    Some package names may not be used in recipes directly, or under some circumstances.

    The full list of package names and their explanations can be found in
    [`conda-forge-pinning-feedstock`](https://github.com/conda-forge/conda-forge-pinning-feedstock/blob/main/recipe/linter_hints/hints.toml).
    """

    kind = "hint"
    identifier = "CF-002"
    message = "${package_hint}"
    package_hint: str
    path: str = "recipe/(meta|recipe).yaml"


@dataclass(kw_only=True)
class NoVariantConfigs(LinterMessage):
    """
    No variant config files could be found in `.ci_support/*.yaml` , which means that
    build matrix is empty and no packages will be built.

    This is usually caused by a misconfiguration of your recipe file (e.g. `build.skip` is always
    `true`, disabling all builds).
    """

    kind = "lint"
    identifier = "CF-003"
    message = (
        "The feedstock has no `.ci_support` files and thus will not build any packages."
    )
    path: str = ".ci_support/*.yaml"


@dataclass(kw_only=True)
class NoEmptyVariantsFile(LinterMessage):
    """
    Variants files can't be empty.
    """

    kind = "lint"
    identifier = "CF-004"
    message = "The recipe should not have an empty `conda_build_config.yaml` file."
    path: str = "recipe/conda_build_config.yaml"


@dataclass(kw_only=True)
class NoCustomGHAWorkflows(LinterMessage):
    """
    Due to its stature in the open-source community, conda-forge has enhanced
    access to certain CI services. This access is a community resource entrusted
    to conda-forge for use in building packages. We thus cannot support
    third-party or "off-label" CI jobs in our feedstocks on any of our CI
    services. If we find such use, we will politely ask the maintainers to
    rectify the situation. We may take more serious actions, including archiving
    feedstocks or removing maintainers from the organization, if the situation
    cannot be rectified.
    """

    kind = "lint"
    identifier = "CF-005"
    message = (
        "conda-forge feedstocks cannot have custom Github Actions workflows. "
        "See https://github.com/conda-forge/conda-forge.github.io/issues/2750 "
        "for more information. If you didn't add any custom workflows, please "
        "consider rerendering your feedstock to remove deprecated workflows."
    )
    path: str = ".github/workflows/*.y*ml"


@dataclass(kw_only=True)
class PinnedDependencyOverridden(LinterMessage):
    """
    Hint when dependency specification overrides a pin.
    """

    kind = "hint"
    identifier = "CF-006"
    added_in = "3.62"
    message = (
        "${output} output overrides versions pinned in the feedstock:\n"
        "${bad_specs_list}\n"
        "Requirement spec should not list version specifiers to respect "
        "conda-forge-pinning. If you need to force another version, "
        "please override the pin via `conda_build_config.yaml`."
    )
    output: str
    bad_specs: dict[str, list[str]]
    path: str = "recipe/(meta|recipe).yaml"

    def _render_attributes(self):
        bad_specs_list = []
        for req_type, specs in self.bad_specs.items():
            specs = [f"`{spec}`" for spec in specs]
            bad_specs_list.append(f"- In section {req_type}: {', '.join(specs)}")
        return {"output": self.output, "bad_specs_list": bad_specs_list}


@dataclass(kw_only=True)
class DeprecatedEnvironmentVariable(LinterMessage):
    """
    Hint when a deprecated environment variable is used.
    """

    kind = "hint"
    identifier = "CF-007"
    added_in = "3.62"
    message = "`${variable}` is deprecated, please use `${replacement}` instead.\n"
    variable: str
    replacement: str


@dataclass(kw_only=True)
class InconclusiveMaintainerCheck(LinterMessage):
    """
    The recipe maintainer existence check could not be completed.

    This happens when GitHub cannot be reached or returns a transient error
    (e.g. a rate limit or a server error) while checking that a maintainer
    listed in `extra.recipe-maintainers` is a valid Github user or
    `@conda-forge/*` team. Rather than risk a false-positive (or
    false-negative), the lint fails and asks for the check to be retried.
    """

    kind = "lint"
    identifier = "CF-008"
    added_in = "2026.6.14"
    message = (
        'Could not verify that recipe maintainer ${team_or}"${maintainer}" '
        "exists due to a transient GitHub error. Please re-run the linter by "
        "commenting `@conda-forge-admin, please lint` on this pull request."
    )
    maintainer: str
    path: str = "recipe/(meta|recipe).yaml"

    def _render_attributes(self):
        return {
            "maintainer": self.maintainer,
            "team_or": "team " if "/" in self.maintainer else "",
        }

    @classmethod
    def examples(cls) -> list[Self]:
        return [
            cls(maintainer="some-user"),
            cls(maintainer="@conda-forge/some-team"),
        ]


@dataclass(kw_only=True)
class WorkflowSettingsPlatformOSMismatch(LinterMessage):
    """
    Lint when a value in `workflow_settings` has mismatched `os` and `platforms`.
    """

    kind = "lint"
    identifier = "CF-009"
    added_in = "TODO"
    message = "`workflow_settings.${setting}[${index}]` restricts `os` to ${os} but `platform` to `${platform}`.\n"
    setting: str
    index: int
    os: list[str]
    platform: list[str]


@dataclass(kw_only=True)
class WorkflowSettingsOverlappingEntries(LinterMessage):
    """
    Lint when there are overlapping entries in `workflow_settings`.
    """

    kind = "lint"
    identifier = "CF-010"
    added_in = "TODO"
    message = "`workflow_settings.${setting} has potentially overlapping entries:\n${entries}.\n"
    setting: str
    entries: list[tuple[str, dict[str, list[str] | None]]]

    def _render_attributes(self):
        return {
            "setting": self.setting,
            "entries": "\n".join(f"[{entry[0]}]={entry[1]}" for entry in self.entries),
        }


@dataclass(kw_only=True)
class WorkflowSettingsNonPlatformSpecificPath(LinterMessage):
    """
    Lint when a path variable in `workflow_settings` is not correctly platform-specific.
    """

    kind = "lint"
    identifier = "CF-011"
    added_in = "TODO"
    message = "`workflow_settings.${setting}[${index}]` specifies path `${value}` without restricting it to Unix / Windows via the `os` or `platform` keys (applies to ${os}).\n"
    setting: str
    index: int
    value: str
    os: list[str]


@dataclass(kw_only=True)
class WorkflowSettingsNonSpecific(LinterMessage):
    """
    Lint when a variable in `workflow_settings` is not correctly restricted to applicable os, platform or provider.
    """

    kind = "lint"
    identifier = "CF-012"
    added_in = "TODO"
    message = "`workflow_settings.${setting}[${index}]` is not restricted by ${mismatched} to applicable workflows (expected: ${restrictions}).\n"
    setting: str
    index: int
    mismatched: list[str]
    restrictions: dict
