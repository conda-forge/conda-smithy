from __future__ import annotations

from functools import wraps
from typing import Any, Callable, List, TypeVar, Type, Optional

T = TypeVar("T")


def _deduplicate_or_empty(input_list: Optional[List[T]]) -> List[T]:
    """
    Deduplicate a list while preserving order. If None is passed, return an empty list.
    """
    if not input_list:
        return []
    return list(dict.fromkeys(input_list))


class LintsHints:
    """
    A container for lints and hints which are automatically deduplicated.
    """

    def __init__(
        self,
        lints: Optional[List[str]] = None,
        hints: Optional[List[str]] = None,
    ):
        self._lints = _deduplicate_or_empty(lints)
        self._hints = _deduplicate_or_empty(hints)

    @property
    def lints(self) -> List[str]:
        """
        Lints are errors.
        """
        return self._lints

    @property
    def hints(self) -> List[str]:
        """
        Hints are suggestions.
        """
        return self._hints

    def __add__(self, other: Any) -> LintsHints:
        if not isinstance(other, LintsHints):
            return NotImplemented
        return LintsHints(
            lints=self.lints + other.lints,
            hints=self.hints + other.hints,
        )

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LintsHints):
            return NotImplemented
        return self.lints == other.lints and self.hints == other.hints

    def append_lint(self, lint: str) -> None:
        if lint in self.lints:
            return
        self.lints.append(lint)

    def append_hint(self, hint: str) -> None:
        if hint in self.hints:
            return
        self.hints.append(hint)

    def extend_lints(self, lints: List[str]) -> None:
        self._lints = _deduplicate_or_empty(self.lints + lints)

    def extend_hints(self, hints: List[str]) -> None:
        self._hints = _deduplicate_or_empty(self.hints + hints)

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


def exceptions_lint(
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
    Use this as an alternative to exceptions_lint for very common exceptions among linting functions.
    """

    pass
