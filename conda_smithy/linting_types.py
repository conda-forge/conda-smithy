from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List


@dataclass
class LintsHints:
    lints: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)

    def __add__(self, other: Any) -> LintsHints:
        if not isinstance(other, LintsHints):
            return NotImplemented
        return LintsHints(
            lints=self.lints + other.lints,
            hints=self.hints + other.hints,
        )


Linter = Callable[[dict], LintsHints]
"""
A Linter is a function taking a dictionary (representing a conda-forge.yml or meta.yaml file)
and returns lints and hints where lints are errors and hints are suggestions.
"""
