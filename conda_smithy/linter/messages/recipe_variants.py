"""
Messages concerning variants configuration (`conda_build_config.yaml`, `variants.yml`)
"""

from dataclasses import dataclass

from conda_smithy.linter.messages.base import _BaseMessage

CATEGORIES = {
    "RC": "All recipe variants files",
    "CBC": "Recipe configuration in `conda_build_config.yaml`",
}

# region RC


@dataclass(kw_only=True)
class RCMacOSDeploymentTargetRename(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "RC-000"
    message = (
        "The `MACOSX_DEPLOYMENT_TARGET` key in {recipe_config_file} needs to be "
        "removed or replaced by `c_stdlib_version`, appropriately restricted to osx"
    )
    recipe_config_file: str


@dataclass(kw_only=True)
class RCMacOSDeploymentTargetBelow(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "RC-001"
    message = (
        "You are setting `c_stdlib_version` on osx below the current global "
        "baseline in conda-forge ({baseline_version})."
    )
    baseline_version: str


@dataclass(kw_only=True)
class RCMoreThanOneFile(_BaseMessage):
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
class CBCMacOSDeploymentTargetConflict(_BaseMessage):
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

@dataclass(kw_only=True)
class CBCMacOSDeploymentTargetBelowStdlib(_BaseMessage):
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
        "conda-forge ({baseline}). If this is the intention, you also need to "
        "override `c_stdlib_version` and `MACOSX_DEPLOYMENT_TARGET` locally."
    )
    baseline: str


# endregion
