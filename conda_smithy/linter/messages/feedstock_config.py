"""
Messages concerning feedstock configuration (`conda-forge.yml`)
"""

from dataclasses import dataclass

from conda_smithy.linter.messages.base import LinterMessage

CATEGORIES = {
    "FC": "Feedstock configuration in `conda-forge.yml`",
}


@dataclass(kw_only=True)
class _CondaForgeYmlMessage:
    """
    A message concerning conda-forge.yml files
    """

    path: str = "conda-forge.yml"


@dataclass(kw_only=True)
class NoDuplicateKeys(LinterMessage, _CondaForgeYmlMessage):
    """
    `conda-forge.yml` must not contain duplicate keys.
    """

    kind = "lint"
    identifier = "FC-001"
    message = "The ``conda-forge.yml`` file is not allowed to have duplicate keys."


@dataclass(kw_only=True)
class OSVersionLower(LinterMessage, _CondaForgeYmlMessage):
    """
    The feedstock has been configured to use an older `os_version` value in `conda-forge.yml`.
    Usually this is needed for _newer_ versions of the Linux image (e.g. opt-in early for
    `alma10` while the default is still `alma9`). In most cases, an older version probably
    means that the override was not updated when the default value caught up.
    """

    kind = "hint"
    identifier = "FC-002"
    message = (
        "The feedstock is lowering the image versions for one or more platforms: ${platforms} "
        "(the default is ${default}). Unless you are in the very rare case of repackaging binary "
        "artifacts, consider removing these overrides from conda-forge.yml "
        "in the top feedstock directory."
    )
    platforms: dict[str, str]
    default: str
