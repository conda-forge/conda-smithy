"""
Messages concerning variants configuration (`conda_build_config.yaml`, `variants.yml`)
"""

from dataclasses import dataclass

from conda_smithy.linter.messages.base import LinterMessage

CATEGORIES = {
    "RC": "All recipe variants files",
    "CBC": "Recipe variants in `conda_build_config.yaml`",
    # None yet, but let's reserve the VC- prefix:
    # "VC": "Recipe variants in `variants.yaml`",
}

# region RC


@dataclass(kw_only=True)
class _ConfigFileMessage:
    """
    A message concerning conda-forge.yml files
    """

    path: str = "recipe/(conda_build_config|variants).yaml"


@dataclass(kw_only=True)
class MacOSDeploymentTargetRename(LinterMessage, _ConfigFileMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "RC-000"
    message = (
        "The `MACOSX_DEPLOYMENT_TARGET` key in ${recipe_config_file} needs to be "
        "removed or replaced by `c_stdlib_version`, appropriately restricted to macOS."
    )
    recipe_config_file: str


@dataclass(kw_only=True)
class MacOSDeploymentTargetBelow(LinterMessage, _ConfigFileMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "RC-001"
    message = (
        "You are setting `c_stdlib_version` on macOS below the current global "
        "baseline in conda-forge (${baseline_version})."
    )
    baseline_version: str


@dataclass(kw_only=True)
class MoreThanOneConfigFile(LinterMessage, _ConfigFileMessage):
    """
    Only one recipe variants file must be used in a feedstock.
    """

    kind = "lint"
    identifier = "RC-002"
    message = (
        "Found two recipe configuration files, but you may only use one! "
        "You may use `conda_build_config.yaml` for both v0 and v1 recipes, "
        "while `variants.yaml` may only be used with v1 recipes."
    )


# endregion
# region CBC


@dataclass(kw_only=True)
class MacOSDeploymentTargetConflict(LinterMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "CBC-000"
    deprecated_in = "3.56.0"
    message = (
        "Conflicting specification for minimum macOS deployment target!\n"
        "If your conda_build_config.yaml sets `MACOSX_DEPLOYMENT_TARGET`, "
        "please change the name of that key to `c_stdlib_version`!\n"
        "Continuing with `max(c_stdlib_version, MACOSX_DEPLOYMENT_TARGET)`."
    )
    path: str = "recipe/conda_build_config.yaml"


@dataclass(kw_only=True)
class MacOSDeploymentTargetBelowStdlib(LinterMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "CBC-001"
    message = (
        "You are setting `MACOSX_SDK_VERSION` below `c_stdlib_version`, "
        "in conda_build_config.yaml which is not possible! Please ensure "
        "`MACOSX_SDK_VERSION` is at least `c_stdlib_version` "
        "(you can leave it out if it is equal).\n"
        "If you are not setting `c_stdlib_version` yourself, this means "
        "you are requesting a version below the current global baseline in "
        "conda-forge (${baseline}). If this is the intention, you also need to "
        "override `c_stdlib_version` and `MACOSX_DEPLOYMENT_TARGET` locally."
    )
    baseline: str
    deprecated_in = "3.56.0"
    path: str = "recipe/conda_build_config.yaml"


# endregion
