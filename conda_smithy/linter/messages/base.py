"""
Collection of linter messages.

If you want to add a lint or a hint, this is where you define the
text, its identifier and the necessary variables.
"""

from dataclasses import asdict
from inspect import cleandoc
from typing import ClassVar, Literal, Self

CATEGORIES: dict[str, str] = {
    "CBC": "Variants configuration (`conda_build_config.yaml`, `variants.yml`)",
    "FC": "Feedstock configuration (`conda-forge.yml`)",
    "R": "All recipe versions",
    "R0": "Recipe v0 (`meta.yaml`)",
    "R1": "Recipe v1 (`recipe.yaml`)",
    "CF": "Issues specific to conda-forge",
}


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
    added_in: ClassVar[str] = "<3.28"
    #: conda-smithy version where the lint was deprecated
    deprecated_in: ClassVar[str] = ""

    @classmethod
    def samples(cls) -> list[Self]:
        """
        Provides one or more example instances of the error message. Used in documentation.
        """
        return []

    def _render(self) -> str:
        """
        Formats the `.message` text by using the dataclass attributes.
        """
        return cleandoc(self.message.format(**self._render_attributes()))

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
