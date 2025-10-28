"""
Collection of linter messages.

If you want to add a lint or a hint, this is where you define the
text, its identifier and the necessary variables.
"""

from dataclasses import asdict, dataclass
from inspect import cleandoc
from pathlib import Path
from typing import ClassVar, Literal


class _BaseMessage:
    """
    A templated message with an identifier.
    """

    #: Shorthand to identify a given error, using two parts: category-instance; e.g. E-100
    identifier: ClassVar[str]
    #: The templated message that will be rendered when converted to string. Subclass with
    #: a property if dynamic behavior is required.
    message: ClassVar[str]
    kind: ClassVar[Literal["lint", "hint"]]

    def template(self) -> str:
        """
        Message to print, whose placeholders will be formatted in .render().

        Subclass if necessary for dynamic behavior.
        Otherwise, it returns the class docstring.
        """
        return self.__doc__

    def render(self) -> str:
        """
        Formats the `.template` text by using the dataclass attributes.
        """
        return cleandoc(self.message.format(**self.render_attributes()))

    def render_attributes(self) -> dict[str, str]:
        """
        Returns attributes rendered as strings. Subclass if necessary.
        """
        return asdict(self)

    def __str__(self) -> str:
        return self.render()


@dataclass(kw_only=True)
class RecipeUnexpectedSection(_BaseMessage):
    """
    Recipe files must not contain unknown top-level keys.
    """

    kind = "lint"
    identifier = "R-000"
    message = "The top level meta key {section} is unexpected"
    section: str


@dataclass(kw_only=True)
class RecipeSectionOrder(_BaseMessage):
    """
    The top-level sections of a recipe file must always follow the same order.
    """

    kind = "lint"
    identifier = "R-001"
    message = "The top level meta keys are in an unexpected order. Expecting {order}."
    order: list[str]

    def render_attributes(self) -> dict[str, str]:
        sections = ", ".join([f"'{section}'" for section in self.order])
        return {"order": f"[{sections}]"}


@dataclass(kw_only=True)
class RecipeMissingAboutItem(_BaseMessage):
    """
    The `about` section requires three fields: homepage (`home` in v1), license, and summary.
    """

    kind = "lint"
    identifier = "R-002"
    message = "The {item} item is expected in the about section."
    item: str


@dataclass(kw_only=True)
class RecipeNoMaintainers(_BaseMessage):
    """
    All recipes must list at least one maintainer under `extra/recipe-maintainers`.
    """

    kind = "lint"
    identifier = "R-003"
    message = (
        "The recipe could do with some maintainers listed in "
        "the `extra/recipe-maintainers` section."
    )


@dataclass(kw_only=True)
class RecipeMaintainersMustBeList(_BaseMessage):
    """
    The `extra/recipe-maintainers` only accepts a list of strings as a value.
    """

    kind = "lint"
    identifier = "R-004"
    message = "Recipe maintainers should be a json list."


@dataclass(kw_only=True)
class RecipeRequiredTests(_BaseMessage):
    """
    All recipes must have a non-empty `test` section.
    """

    kind = "lint"
    identifier = "R-005"
    message = "The recipe must have some tests."


@dataclass(kw_only=True)
class RecipeRecommendedTests(_BaseMessage):
    """
    All recipes must have a non-empty `test` section.
    """

    kind = "hint"
    identifier = "R-006"
    message = "It looks like the '{output}' output doesn't have any tests."
    output: str


@dataclass(kw_only=True)
class RecipeUnknownLicense(_BaseMessage):
    """
    All recipes must have a license identifier, but it can't be "unknown".
    """

    kind = "lint"
    identifier = "R-007"
    message = "The recipe license cannot be unknown."


@dataclass(kw_only=True)
class RecipeFormattedSelectors(_BaseMessage):
    """
    Recipe format v0 (`meta.yaml`) supports the notion of line selectors
    as trailing comments:

    ```yaml
    build:
      skip: true  # [not win]
    ```

    These must be formatted with two spaces before the `#` symbol, followed
    by one space before the opening square bracket `[`, followed by no spaces.
    The closing bracket must not be surrounded by spaces either.
    """

    kind = "lint"
    identifier = "R0-001"
    message = (
        "Selectors are suggested to take a "
        "``<two spaces>#<one space>[<expression>]`` form."
        " See lines {lines}"
    )
    lines: list[str]


@dataclass(kw_only=True)
class RecipeOldPythonSelectorsLint(_BaseMessage):
    """
    Recipe v0 selectors used to include one Python version selector
    per release, like `py27` for Python 2.7 and `py35` for Python 3.5.
    This was deprecated in favor of the `py` integer, which is preferred.
    """

    kind = "lint"
    identifier = "R0-002"
    message = (
        "Old-style Python selectors (py27, py35, etc) are only available "
        "for Python 2.7, 3.4, 3.5, and 3.6. Please use explicit comparisons "
        "with the integer ``py``, e.g. ``# [py==37]`` or ``# [py>=37]``. "
        "See lines {lines}"
    )
    lines: list[str]


@dataclass(kw_only=True)
class RecipeOldPythonSelectorsHint(_BaseMessage):
    """
    Recipe v0 selectors (see [`R0-002`](#r0-002)) used to include one Python
    version selector per release, like `py27` for Python 2.7 and `py35` for Python 3.5.
    This was deprecated in favor of the `py` integer, which is preferred.
    """

    kind = "hint"
    identifier = "R0-003"
    message = (
        "Old-style Python selectors (py27, py34, py35, py36) are "
        "deprecated. Instead, consider using the int ``py``. For "
        "example: ``# [py>=36]``. See lines {lines}"
    )
    lines: list[str]


def generate_docs(output_file: str | None = None) -> str:
    if output_file is None:
        # Let's check if we are in a repo or installed
        maybe_repo_root = Path(__file__).parents[2]
        if (maybe_repo_root / "README.md").is_file() and (maybe_repo_root / ".git").is_dir():
            output_file = maybe_repo_root / "LINTER.md"

    def collect_messages():
        current_globals = globals().copy()
        for obj_name, obj in current_globals.items():
            if obj_name.startswith("_"):
                continue
            try:
                if issubclass(obj, _BaseMessage):
                    yield obj
            except TypeError:
                pass

    lines = ["# Linter messages", ""]
    identifiers = set()
    for cls in sorted(collect_messages(), key=lambda obj: obj.identifier):
        if cls.identifier in identifiers:
            raise ValueError(f"Duplicate identifier: {cls.identifier}.")
        identifiers.add(cls.identifier)
        lines.extend(
            [
                f"<a id='{cls.identifier}'></a>",
                f"## `{cls.identifier}`: `{cls.__name__}`",
                "",
                "",
                cleandoc(cls.__doc__),
                "",
                (
                    f"<details>\n\n<summary>{cls.kind.title()} message</summary>\n\n"
                    f"```text\n{cls.message}\n```\n\n</details>"
                ),
                "",
            ]
        )

    text = "\n".join(lines)
    if output_file:
        with open(output_file, "w") as f:
            f.write(text)
    return text


if __name__ == "__main__":
    print(generate_docs())
