"""
Messages exclusive to conda-forge recipes.
"""

from dataclasses import dataclass

from conda_smithy.linter.messages.base import _BaseMessage

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
    message = 'Recipe maintainer {team_or}"{maintainer}" does not exist'
    maintainer: str

    def _render_attributes(self):
        return {
            "maintainer": self.maintainer,
            "team_or": "team " if "/" in self.maintainer else "",
        }


@dataclass(kw_only=True)
class CFPackageToAvoid(_BaseMessage):
    """
    Some package names may not be used in recipes directly, or under some circumstances.

    The full list of package names and their explanations can be found in
    [`conda-forge-pinning-feedstock`](https://github.com/conda-forge/conda-forge-pinning-feedstock/blob/main/recipe/linter_hints/hints.toml).
    """

    kind = "hint"
    identifier = "CF-002"
    message = "{package_hint}"
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
    identifier = "CF-004"
    message = (
        "The feedstock has no `.ci_support` files and thus will not build any packages."
    )
