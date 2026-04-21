"""
Messages concerning feedstock configuration (`conda-forge.yml`)
"""

from dataclasses import dataclass

from conda_smithy.linter.messages.base import LinterMessage

CATEGORIES = {
    "FC": "Feedstock configuration in `conda-forge.yml`",
}


@dataclass(kw_only=True)
class NoDuplicateKeys(LinterMessage):
    """
    `conda-forge.yml` must not contain duplicate keys.
    """

    kind = "lint"
    identifier = "FC-001"
    message = "The ``conda-forge.yml`` file is not allowed to have duplicate keys."
