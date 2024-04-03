from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, TypeVar

T = TypeVar("T")


@dataclass
class LintsHints:
    lints: List[str] = field(default_factory=list)
    """
    Lints are errors.
    """
    hints: List[str] = field(default_factory=list)
    """
    Hints are suggestions.
    """

    def __add__(self, other: Any) -> LintsHints:
        if not isinstance(other, LintsHints):
            return NotImplemented
        return LintsHints(
            lints=self.lints + other.lints,
            hints=self.hints + other.hints,
        )

    def append_lint(self, lint: str) -> None:
        self.lints.append(lint)

    def append_hint(self, hint: str) -> None:
        self.hints.append(hint)

    @classmethod
    def lint(cls, lint: str) -> LintsHints:
        """
        Shortcut to create a LintsHints object with a single lint.
        """
        return cls(lints=[lint])

    @classmethod
    def hint(cls, hint: str) -> LintsHints:
        """
        Shortcut to create a LintsHints object with a single hint.
        """
        return cls(hints=[hint])


Linter = Callable[[dict, T], LintsHints]
"""
A Linter is a function taking a dictionary (representing a conda-forge.yml or meta.yaml file) as well as extra data
and returns a LintsHints object.
The generic type T of the Linter is the type of extra data that is passed to the linter.
"""
