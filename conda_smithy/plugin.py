"""Conda plugin hooks for conda-smithy.

Registers ``conda smithy`` so the feedstock tooling is available as a conda
subcommand when this package is installed in the same environment as conda.
"""

from __future__ import annotations

from conda.plugins import hookimpl
from conda.plugins.types import CondaSubcommand


def _execute(args: tuple[str, ...]) -> int | None:
    """Dispatch plugin arguments to the smithy CLI.

    Lazy import to avoid import-time side effects when not using conda-smithy.
    """
    from conda_smithy.cli import main

    return main(args)


@hookimpl
def conda_subcommands():
    yield CondaSubcommand(
        name="smithy",
        summary=(
            "Help create, administer and manage conda-forge feedstocks "
            "(https://github.com/conda-forge/conda-smithy)."
        ),
        action=_execute,
    )
