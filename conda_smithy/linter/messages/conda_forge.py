"""
Messages exclusive to conda-forge recipes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from conda_smithy.linter.messages.base import _BaseMessage

if TYPE_CHECKING:
    from typing import Self

CATEGORIES = {
    "CF": "conda-forge specific rules",
}


@dataclass(kw_only=True)
class CFMaintainerExists(_BaseMessage):
    """
    Maintainers listed in `extra.recipe-maintainers` must be valid Github usernames
    or `@conda-forge/*` teams.
    """

    kind = "lint"
    identifier = "CF-001"
    message = 'Recipe maintainer ${team_or}"${maintainer}" does not exist'
    maintainer: str

    def _render_attributes(self):
        return {
            "maintainer": self.maintainer,
            "team_or": "team " if "/" in self.maintainer else "",
        }

    @classmethod
    def samples(cls) -> list[Self]:
        return [
            cls(maintainer="@banned-user"),
            cls(maintainer="@conda-forge/deleted-team"),
        ]


@dataclass(kw_only=True)
class CFPackageToAvoid(_BaseMessage):
    """
    Some package names may not be used in recipes directly, or under some circumstances.

    The full list of package names and their explanations can be found in
    [`conda-forge-pinning-feedstock`](https://github.com/conda-forge/conda-forge-pinning-feedstock/blob/main/recipe/linter_hints/hints.toml).
    """

    kind = "hint"
    identifier = "CF-002"
    message = "${package_hint}"
    package_hint: str


@dataclass(kw_only=True)
class CFNoCiSupport(_BaseMessage):
    """
    No `.ci_support/*.yaml` files could be found, which means that build matrix is empty
    and no packages will be built.

    This is usually caused by a misconfiguration of your recipe file (e.g. `build.skip` is always
    `true`, disabling all builds).
    """

    kind = "lint"
    identifier = "CF-003"
    message = (
        "The feedstock has no `.ci_support` files and thus will not build any packages."
    )


@dataclass(kw_only=True)
class CFNoEmptyVariantsFile(_BaseMessage):
    """
    Variants files can't be empty.
    """

    kind = "lint"
    identifier = "CF-004"
    message = "The recipe should not have an empty `conda_build_config.yaml` file."


@dataclass(kw_only=True)
class CFNoCustomGHAWorkflows(_BaseMessage):
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
