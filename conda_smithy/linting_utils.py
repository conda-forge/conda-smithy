from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, List, TypeVar, Type

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


def lint_exceptions(
    *_exceptions: Type[Exception],
) -> Callable[[Linter[T]], Linter[T]]:
    """
    A decorator factory to catch exceptions raised by a linter and return them as lints.
    :param _exceptions: the exceptions to catch
    """

    def lint_exceptions_decorator(linter: Linter[T]) -> Linter[T]:
        @wraps(linter)
        def linter_wrapper(data: dict, extras: T) -> LintsHints:
            try:
                return linter(data, extras)
            except _exceptions as e:
                return LintsHints.lint(str(e))

        return linter_wrapper

    return lint_exceptions_decorator


class AutoLintException(Exception):
    """
    An exception that is automatically converted to a lint by lint_recipe._lint.
    Use this as an alternative to lint_exceptions for very common exceptions among linting functions.
    """

    pass
