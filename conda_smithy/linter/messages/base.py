"""
Collection of linter messages.

If you want to add a lint or a hint, this is where you define the
text, its identifier and the necessary variables.
"""

from dataclasses import asdict
from inspect import cleandoc
from string import Template
from typing import ClassVar, Literal, Self


class _BaseMessage:
    """
    A templated message with an identifier.

    The error message shown to the user by conda-smithy lint is contained in the
    `message` attribute.

    The docstring should contain longer-form details that will be used
    to auto-generate documentation pages. This docstring should explain:

    - What's wrong
    - Why that's a problem
    - How to fix it (with examples)
    """

    #: Shorthand to identify a given error, using two parts: category-instance; e.g. E-100
    identifier: ClassVar[str]
    #: The templated message that will be rendered when converted to string. Subclass with
    #: a property if dynamic behavior is required.
    message: ClassVar[str]
    #: Whether the problem is a lint (error) or a hint (warning)
    kind: ClassVar[Literal["lint", "hint"]]
    #: conda-smithy version where the lint introduced
    added_in: ClassVar[str] = "<3.56"
    #: conda-smithy version where the lint was deprecated
    deprecated_in: ClassVar[str] = ""

    @classmethod
    def samples(cls) -> list[Self]:
        """
        Provides one or more example instances of the error message. Used in documentation.
        Define at least one if `message` needs to be rendered with additional attributes.
        Not needed for static `message` strings.
        """
        return []

    def _render(self) -> str:
        """
        Formats the `.message` text by using the dataclass attributes.

        Uses `string.Template.safe_substitute`, so `$name` and `${name}` are
        replacement fields. Curly braces are never interpreted and need no
        escaping. Unrecognised ``$name`` tokens are left as-is by
        ``safe_substitute``, so a bare ``$`` only needs to be written as ``$$``
        when it is immediately followed by a valid identifier that is also a
        key in ``_render_attributes()`` and must not be substituted.
        """
        return cleandoc(
            Template(self.message).safe_substitute(self._render_attributes())
        )

    def _render_attributes(self) -> dict[str, str]:
        """
        Returns attributes rendered as strings. Subclass if necessary.
        """
        return asdict(self)

    def __str__(self) -> str:
        return self._render()

    def append_if_absent(
        self, iterable: list, test: Literal["isinstance", "str"] = "isinstance"
    ) -> None:
        if test == "isinstance":
            test = lambda a, b: isinstance(a, b.__class__)
        elif test == "str":
            test = lambda a, b: str(a) == str(b)
        else:
            raise ValueError("`test` must be either 'isinstance' or 'str'")

        if any(test(item, self) for item in iterable):
            return
        iterable.append(self)
