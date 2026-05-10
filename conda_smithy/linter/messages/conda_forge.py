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
    message = (
        "${output} output overrides versions pinned in the feedstock:\n"
        "${bad_specs_list}\n"
        "Requirement spec should not list version specifiers to respect "
        "conda-forge-pinning. If you need to force another version, "
        "please override the pin via `conda_build_config.yaml`."
    )
    output: str
    bad_specs: dict[str, list[str]]

    def _render_attributes(self):
        bad_specs_list = []
        for req_type, specs in self.bad_specs.items():
            specs = [f"`{spec}`" for spec in specs]
            bad_specs_list.append(f"- In section {req_type}: {', '.join(specs)}")
        return {"output": self.output, "bad_specs_list": bad_specs_list}
