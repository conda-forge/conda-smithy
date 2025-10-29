"""
Collection of linter messages.

If you want to add a lint or a hint, this is where you define the
text, its identifier and the necessary variables.
"""

from dataclasses import asdict, dataclass
from inspect import cleandoc
from pathlib import Path
from typing import ClassVar, Literal

CATEGORIES: dict[str, str] = {
    "CBC": "Variants configuration (`conda_build_config.yaml`)",
    "FC": "Feedstock configuration (`conda-forge.yml`)",
    "R": "All recipe versions",
    "R0": "Recipe v0 (`meta.yaml`)",
    "R1": "Recipe v1 (`recipe.yaml`)",
    "CF": "Recipe issues specific to conda-forge",
}


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


@dataclass(kw_only=True)
class RecipeNoCommentSelectors(_BaseMessage):
    """
    Recipe v0 selectors (see [`R0-002`](#r0-002)) are not supported in v1 recipes.
    """

    kind = "lint"
    identifier = "R1-001"
    message = (
        "Selectors in comment form no longer work in v1 recipes. Instead,"
        " if / then / else maps must be used. See lines {lines}."
    )
    lines: list[str]


@dataclass(kw_only=True)
class RecipeBuildNumberMissing(_BaseMessage):
    """
    All recipes must define a `build.number` value.
    """

    kind = "lint"
    identifier = "R-008"
    message = "The recipe must have a `build/number` section."


@dataclass(kw_only=True)
class RecipeRequirementsOrder(_BaseMessage):
    """
    The different subcategories of the `requirements` section must follow
    a strict order: `build`, `host`, `run`, `run_constrained`.
    """

    kind = "lint"
    identifier = "R-009"
    message = (
        "The `requirements/` sections should be defined "
        "in the following order: {expected}; instead saw: {seen}."
    )
    expected: list[str]
    seen: list[str]

    def render_attributes(self):
        return {
            "expected": ", ".join(self.expected),
            "seen": ", ".join(self.seen),
        }


@dataclass(kw_only=True)
class RecipeLicenseLicense(_BaseMessage):
    """
    Licenses should omit the term 'License' in its name.
    """

    kind = "lint"
    identifier = "R-010"
    message = 'The recipe `license` should not include the word "License".'


@dataclass(kw_only=True)
class RecipeTooManyEmptyLines(_BaseMessage):
    """
    Recipe files should end with a single empty line, not more.
    """

    kind = "lint"
    identifier = "R-011"
    message = (
        "There are {n_lines} too many lines.  "
        "There should be one empty line at the end of the "
        "file."
    )
    n_lines: int


@dataclass(kw_only=True)
class RecipeTooFewEmptyLines(_BaseMessage):
    """
    Recipe files should end with a single empty line.
    """

    kind = "lint"
    identifier = "R-012"
    message = (
        "There are too few lines.  There should be one empty "
        "line at the end of the file."
    )


@dataclass(kw_only=True)
class RecipeLicenseFamily(_BaseMessage):
    """
    The field `license_file` must be always present.
    """

    kind = "lint"
    identifier = "R-013"
    message = "license_file entry is missing, but is required."


@dataclass(kw_only=True)
class RecipeName(_BaseMessage):
    """
    The recipe `name` can only contain certain characters:

    - lowercase ASCII letters (`a-z`)
    - digits (`0-9`)
    - underscores, hyphens and dots (`_`, `-`, `.`)
    """

    kind = "lint"
    identifier = "R-014"
    message = (
        "Recipe name has invalid characters. only lowercase alpha, "
        "numeric, underscores, hyphens and dots allowed"
    )


@dataclass(kw_only=True)
class RecipeMissingVersion(_BaseMessage):
    """
    The package `version` field is required.
    """

    kind = "lint"
    identifier = "R-015"
    message = "Package version is missing."


@dataclass(kw_only=True)
class RecipeInvalidVersion(_BaseMessage):
    """
    The package `version` field must be a valid version string.
    """

    kind = "lint"
    identifier = "R-016"
    message = "Package version {version} doesn't match conda spec: {error}"
    version: str
    error: str


@dataclass(kw_only=True)
class RecipePinnedNumpy(_BaseMessage):
    """
    See <https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy>
    """

    kind = "lint"
    identifier = "R-017"
    message = (
        "Using pinned numpy packages is a deprecated pattern.  Consider "
        "using the method outlined "
        "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy)."
    )


@dataclass(kw_only=True)
class RecipeUnexpectedSubsection(_BaseMessage):
    """
    This check ensures that the passed recipe conforms to the expected recipe v0 schema.

    See schema in [`conda_build.metadata.FIELDS`](
    https://github.com/conda/conda-build/blob/25.9.0/conda_build/metadata.py#L619)
    """

    kind = "lint"
    identifier = "R-018"
    message = (
        "The {section} section contained an unexpected subsection name. "
        "{subsection} is not a valid subsection name."
    )
    section: str
    subsection: str


@dataclass(kw_only=True)
class RecipeSourceHash(_BaseMessage):
    """
    All recipe source URLs must have a hash checksum for integrity checks.
    """

    kind = "lint"
    identifier = "R-019"
    message = (
        "When defining a source/url please add a sha256, sha1 "
        "or md5 checksum (sha256 preferably)."
    )


@dataclass(kw_only=True)
class RecipeNoarchValue(_BaseMessage):
    """
    The `build.noarch` field can only take `python` or `generic` as a value.
    """

    kind = "lint"
    identifier = "R-020"
    valid: ClassVar[list[str]] = ["python", "generic"]
    message = "Invalid `noarch` value `{given}`. Should be one of `{valid}`."
    given: str

    def render_attributes(self):
        return {"given": self.given, "valid": ", ".join(self.valid)}


@dataclass(kw_only=True)
class RecipeNoarchSelectorsV0(_BaseMessage):
    """
    Noarch packages are not generally compatible with v0 selectors
    """

    kind = "lint"
    identifier = "R0-004"
    message = (
        "`noarch` packages can't have {skips}selectors. If "
        "the selectors are necessary, please remove "
        "`noarch: {noarch}`, or selector on line {line_number}:"
        "\n{line}"
    )
    noarch: str
    line_number: int
    line: str
    skips: bool = False

    def render_attributes(self):
        attrs = asdict(self)
        attrs["skips"] = "skips with " if self.skips else ""
        return attrs


@dataclass(kw_only=True)
class RecipeNoarchSelectorsV1(_BaseMessage):
    """
    Noarch packages are not generally compatible with v1 conditional blocks.
    """

    kind = "lint"
    identifier = "R1-002"
    message = (
        "`noarch` packages can't have {skips}selectors. If "
        "the selectors are necessary, please remove "
        "`noarch: {noarch}`."
    )
    noarch: str
    skips: bool = False

    def render_attributes(self):
        return {"noarch": self.noarch, "skips": "skips with " if self.skips else ""}


@dataclass(kw_only=True)
class RecipeJinjaDefinitions(_BaseMessage):
    """
    In v0 recipes, Jinja definitions must follow a particular style.
    """

    kind = "lint"
    identifier = "R0-005"
    message = (
        "Jinja2 variable definitions are suggested to "
        "take a ``{{%<one space>set<one space>"
        "<variable name><one space>=<one space>"
        "<expression><one space>%}}`` form. See lines {lines}"
    )
    lines: list[int]


@dataclass(kw_only=True)
class RecipeLegacyToolchain(_BaseMessage):
    """
    The `toolchain` package is deprecated. Use compilers as outlined in
    <https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers>.
    """

    kind = "lint"
    identifier = "R0-006"
    message = (
        "Using toolchain directly in this manner is deprecated.  Consider "
        "using the compilers outlined "
        "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers)."
    )


@dataclass(kw_only=True)
class RecipeRequirementJoinVersionOperator(_BaseMessage):
    """
    conda recipes should use the three-field matchspec syntax to express requirements:
    `name [version [build]]`. This means having no spaces between operator and version
    literals.
    """

    kind = "lint"
    identifier = "R-021"
    message = (
        "``requirements: {section}: {requirement}`` should not "
        "contain a space between relational operator and the version, i.e. "
        "``{name} {pin}``"
    )
    section: str
    requirement: str
    name: str
    pin: str


@dataclass(kw_only=True)
class RecipeRequirementSeparateNameVersion(_BaseMessage):
    """
    conda recipes should use the three-field matchspec syntax to express requirements:
    `name [version [build]]`. This means having a space between name and version.
    """

    kind = "lint"
    identifier = "R-022"
    message = (
        "``requirements: {section}: {requirement}`` must "
        "contain a space between the name and the pin, i.e. "
        "``{name} {pin}``"
    )
    section: str
    requirement: str
    name: str
    pin: str


@dataclass(kw_only=True)
class RecipeLanguageHostRun(_BaseMessage):
    """
    Packages may depend on certain languages (e.g. Python, R) that require depending
    on the language runtime both in `host` and `run`.
    """

    kind = "lint"
    identifier = "R-023"
    message = "If {language} is a host requirement, it should be a run requirement."
    language: str


@dataclass(kw_only=True)
class RecipeLanguageHostRunUnpinned(_BaseMessage):
    """
    Packages may depend on certain languages (e.g. Python, R) that require depending
    on the language runtime both in `host` and `run`. They should not pin it to a
    particular version when the package is not `noarch`.
    """

    kind = "lint"
    identifier = "R-024"
    message = (
        "Non noarch packages should have {language} requirement "
        "without any version constraints."
    )
    language: str


@dataclass(kw_only=True)
class RecipeJinjaExpression(_BaseMessage):
    """
    Jinja expressions should add a space between the double curly braces.
    """

    kind = "hint"
    identifier = "R-025"
    message = (
        "Jinja2 variable references are suggested to "
        "take a ``{dollar}{{{{<one space><variable name><one space>}}}}`` "
        "form. See lines {lines}."
    )
    recipe_version: Literal[0, 1]
    lines: list[int]

    def render_attributes(self):
        return {"dollar": "$" if self.recipe_version == 1 else "", "lines": self.lines}


@dataclass(kw_only=True)
class RecipePythonLowerBound(_BaseMessage):
    """
    Noarch Python recipes should always pin the lower bound on their `python` requirement.
    """

    kind = "lint"
    identifier = "R-026"
    message = (
        "noarch: python recipes are required to have a lower bound "
        "on the python version. Typically this means putting "
        "`python >={{{{ python_min }}}}` in the `run` section of your "
        "recipe. You may also want to check the upstream source "
        "for the package's Python compatibility."
    )


@dataclass(kw_only=True)
class RecipePinSubpackagePinCompatible(_BaseMessage):
    """
    The Jinja functions `pin_subpackage` and `pin_compatible` may be confused
    because both would add version constraints to a package name. However, they
    have different purposes.

    - `pin_subpackage()` must be used when the package to be pinned is a known output
      in the current recipe.
    - `pin_compatible()` must be used when the package to be pinned is _not_ an output
      of the current recipe.
    """

    kind = "lint"
    identifier = "R-027"
    message = (
        "{should_use} should be used instead of {in_use} for `{pin}` "
        "because it is {what} known outputs of this recipe: {subpackages}."
    )
    in_use: str
    should_use: str
    pin: str
    subpackages: list[str]
    is_output: bool

    def render_attributes(self):
        attrs = asdict(self)
        is_output = attrs.pop("is_output")
        attrs["what"] = "one of the" if is_output else "not a"
        return attrs


@dataclass(kw_only=True)
class RecipeCompiledWheelsNotAllowed(_BaseMessage):
    """
    Python wheels are often discouraged as package sources. This is especially the case
    for compiled wheels, which are forbidden.
    """

    kind = "lint"
    identifier = "R-028"
    message = (
        "Detected compiled wheel(s) in source: {urls}. "
        "This is disallowed. All packages should be built from source except in "
        "rare and exceptional cases."
    )
    urls: list[str]

    def render_attributes(self):
        return {"urls": ", ".join([f"`{url}`" for url in self.urls])}


@dataclass(kw_only=True)
class RecipePureWheelsNotAllowed(_BaseMessage):
    """
    Python wheels are often discouraged as package sources. This is also the case
    for pure Python wheels when building non-noarch packages.
    """

    kind = "lint"
    identifier = "R-029"
    message = (
        "Detected pure Python wheel(s) in source: {urls}. "
        "This is discouraged. Please consider using a source distribution (sdist) instead."
    )
    urls: list[str]

    def render_attributes(self):
        return {"urls": ", ".join([f"`{url}`" for url in self.urls])}


@dataclass(kw_only=True)
class RecipePureWheelsNotAllowedNoarch(_BaseMessage):
    """
    Python wheels are often discouraged as package sources. However, pure Python
    wheels may be used as a source for noarch Python packages, although sdists are preferred.
    """

    kind = "hint"
    identifier = "R-030"
    message = (
        "Detected pure Python wheel(s) in source: {urls}. "
        "This is generally ok for pure Python wheels and noarch=python "
        "packages but it's preferred to use a source distribution (sdist) if possible."
    )
    urls: list[str]

    def render_attributes(self):
        return {"urls": ", ".join([f"`{url}`" for url in self.urls])}


@dataclass(kw_only=True)
class RecipeRustLicenses(_BaseMessage):
    """
    <https://conda-forge.org/docs/maintainer/adding_pkgs/#rust>
    """

    kind = "lint"
    identifier = "R-031"
    message = (
        "Rust packages must include the licenses of the Rust dependencies. "
        "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust"
    )


@dataclass(kw_only=True)
class RecipeGoLicenses(_BaseMessage):
    """
    <https://conda-forge.org/docs/maintainer/adding_pkgs/#go>
    """

    kind = "lint"
    identifier = "R-032"
    message = (
        "Go packages must include the licenses of the Go dependencies. "
        "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go"
    )


@dataclass(kw_only=True)
class RecipeStdlibJinja(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "R-033"
    message = (
        "This recipe is using a compiler, which now requires adding a build "
        'dependence on `{dollar}{{{{ stdlib("c") }}}}` as well. Note that this rule applies to '
        "each output of the recipe using a compiler. For further details, please "
        "see https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    recipe_version: Literal[0, 1]

    def render_attributes(self):
        return {"dollar": "$" if self.recipe_version == 1 else ""}


@dataclass(kw_only=True)
class RecipeStdlibSysroot(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "R-034"
    message = (
        "You're setting a requirement on sysroot_linux-<arch> directly; this should "
        'now be done by adding a build dependence on `{dollar}{{{{ stdlib("c") }}}}`, and '
        "overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for the "
        "respective platform as necessary. For further details, please see "
        "https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    recipe_version: Literal[0, 1]

    def render_attributes(self):
        return {"dollar": "$" if self.recipe_version == 1 else ""}


@dataclass(kw_only=True)
class RecipeStdlibOsx(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "R-035"
    message = (
        "You're setting a constraint on the `__osx` virtual package directly; this "
        'should now be done by adding a build dependence on `{dollar}{{{{ stdlib("c") }}}}`, '
        "and overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for "
        "the respective platform as necessary. For further details, please see "
        "https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    recipe_version: Literal[0, 1]

    def render_attributes(self):
        return {"dollar": "$" if self.recipe_version == 1 else ""}


@dataclass(kw_only=True)
class CBCMacOSDeploymentTargetConflict(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "CBC-000"
    message = (
        "Conflicting specification for minimum macOS deployment target!\n"
        "If your conda_build_config.yaml sets `MACOSX_DEPLOYMENT_TARGET`, "
        "please change the name of that key to `c_stdlib_version`!\n"
        "Continuing with `max(c_stdlib_version, MACOSX_DEPLOYMENT_TARGET)`."
    )


@dataclass(kw_only=True)
class CBCMacOSDeploymentTargetRename(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "CBC-001"
    message = (
        "In your conda_build_config.yaml, please change the name of "
        "`MACOSX_DEPLOYMENT_TARGET`, to `c_stdlib_version`!"
    )


@dataclass(kw_only=True)
class CBCMacOSDeploymentTargetBelow(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "CBC-002"
    message = (
        "You are setting `c_stdlib_version` below the current global baseline "
        "in conda-forge (10.13). If this is your intention, you also need to "
        "override `MACOSX_DEPLOYMENT_TARGET` (with the same value) locally."
    )


@dataclass(kw_only=True)
class CBCMacOSDeploymentTargetBelowStdlib(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "CBC-003"
    message = (
        "You are setting `MACOSX_SDK_VERSION` below `c_stdlib_version`, "
        "in conda_build_config.yaml which is not possible! Please ensure "
        "`MACOSX_SDK_VERSION` is at least `c_stdlib_version` "
        "(you can leave it out if it is equal).\n"
        "If you are not setting `c_stdlib_version` yourself, this means "
        "you are requesting a version below the current global baseline in "
        "conda-forge (10.13). If this is the intention, you also need to "
        "override `c_stdlib_version` and `MACOSX_DEPLOYMENT_TARGET` locally."
    )


@dataclass(kw_only=True)
class RecipeNotParsableLint(_BaseMessage):
    """
    The conda recipe should be parsable by at least one backend.
    If none can parse it, this constitutes an error that needs to be remediated.
    """

    kind = "lint"
    identifier = "R-036"
    message = (
        "The recipe is not parsable by any of the known "
        "recipe parsers ({parsers}). Please "
        "check the logs for more information and ensure your "
        "recipe can be parsed."
    )
    parsers: list[str]

    def render_attributes(self):
        return {"parsers": sorted(self.parsers)}


@dataclass(kw_only=True)
class RecipeNotParsableHint(_BaseMessage):
    """
    The conda recipe should be parsable by at least one backend.
    Sometimes, only some backends fail, which is not critical, but should be looked into.
    """

    kind = "hint"
    identifier = "R-037"
    parser: str

    @property
    def message(self):
        msg = f"The recipe is not parsable by parser `{self.parser}`. "
        if self.parser == "conda-souschef (grayskull)":
            msg += (
                "This parser is not currently used by conda-forge, but may be in the future. "
                "We are collecting information to see which recipes are compatible with grayskull."
            )
        elif self.parser == "conda-recipe-manager":
            msg += (
                "The recipe can only be automatically migrated to the new v1 format "
                "if it is parseable by conda-recipe-manager."
            )
        else:
            msg += (
                "Your recipe  may not receive automatic updates and/or may not be compatible "
                "with conda-forge's infrastructure. Please check the logs for "
                "more information and ensure your recipe can be parsed."
            )
        return msg


@dataclass(kw_only=True)
class RecipePythonIsAbi3Bool(_BaseMessage):
    """
    https://github.com/conda-forge/conda-forge.github.io/issues/2102
    """

    kind = "lint"
    identifier = "R-038"
    message = (
        "The `is_abi3` variant variable is now a boolean value instead of a "
        "string (i.e., 'true' or 'false'). Please change syntax like "
        "`is_abi3 == 'true' to `is_abi3`."
    )


@dataclass(kw_only=True)
class CFMaintainerExists(_BaseMessage):
    """
    Maintainers listed in `extra.recipe-maintainers` must be valid Github usernames
    or `@conda-forge/*` teams.
    """

    kind = "lint"
    identifier = "CF-001"
    message = 'Recipe maintainer {team_or}"{maintainer}" does not exist'
    maintainer: str

    def render_attributes(self):
        return {
            "maintainer": self.maintainer,
            "team_or": "team " if "/" in self.maintainer else "",
        }


@dataclass(kw_only=True)
class CFPackageToAvoid(_BaseMessage):
    """
    Some package names may not be used in recipes directly, or under some circumstances.

    The full list of package names and their explanations can be found in
    [`conda-forge-pinning-feedstock`](https://github.com/conda-forge/conda-forge-pinning-feedstock/blob/main/recipe/linter_hints/hints.toml).
    """

    kind = "hint"
    identifier = "CF-002"
    message = "{package_hint}"
    package_hint: str


@dataclass(kw_only=True)
class CFNoCiSupport(_BaseMessage):
    """
    No `.ci_support/*.yaml` files could be found, which means that build matrix is empty
    and no packages will be built.

    This is usually caused by a misconfiguration of your recipe file (e.g. `build.skip` is always
    `true`, disabling all builds).
    """

    kind = "lint"
    identifier = "CF-004"
    message = (
        "The feedstock has no `.ci_support` files and thus will not build any packages."
    )


@dataclass(kw_only=True)
class FCNoDuplicateKeys(_BaseMessage):
    """
    `conda-forge.yml` must not contain duplicate keys.
    """

    kind = "lint"
    identifier = "FC-001"
    message = "The ``conda-forge.yml`` file is not allowed to have duplicate keys."


@dataclass(kw_only=True)
class RecipeUsePip(_BaseMessage):
    """
    Python packages should be built with `pip install ...`, not `python setup.py install`,
    which is deprecated.
    """

    kind = "hint"
    identifier = "R-039"
    message = (
        "Whenever possible python packages should use pip. "
        "See https://conda-forge.org/docs/maintainer/adding_pkgs.html#use-pip"
    )


@dataclass(kw_only=True)
class RecipeUsePyPiOrg(_BaseMessage):
    """
    Grayskull and the conda-forge example recipe used to have pypi.io as a default,
    but the canonical URL is now PyPI.org.

    See https://github.com/conda-forge/staged-recipes/pull/27946.
    """

    kind = "hint"
    identifier = "R-040"
    message = (
        "PyPI default URL is now pypi.org, and not pypi.io."
        " You may want to update the default source url."
    )


@dataclass(kw_only=True)
class RecipeSuggestNoarch(_BaseMessage):
    """
    `noarch` packages are strongly preferred when possible.
    See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds.
    """

    kind = "hint"
    identifier = "R-041"
    message = (
        "Whenever possible python packages should use noarch. "
        "See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds"
    )


@dataclass(kw_only=True)
class ScriptShellcheckReport(_BaseMessage):
    """
    This issue is raised when `shellcheck` is enabled and detects problems
    in your build `.sh` scripts.

    See https://www.shellcheck.net/wiki/ for details on the shellcheck error codes.
    """

    kind = "hint"
    identifier = "R-042"
    max_lines: ClassVar[int] = 50
    command: list[str] | None = None
    output_lines: list[str] | None = None

    @property
    def message(self):
        # All files successfully scanned with some issues.
        joined_cmd = " ".join(self.command)
        lines = [
            "Whenever possible fix all shellcheck findings "
            f"('{joined_cmd}' recipe/*.sh -f diff | git apply' helps)",
            *self.output_lines[:50],
        ]
        if len(self.output_lines) > self.max_lines:
            lines.append(
                "Output restricted, there are "
                f"'{len(self.output_lines) - self.max_lines}' more lines."
            )
        return "\n".join(lines).replace("{", "{{").replace("}", "}}")


@dataclass(kw_only=True)
class ScriptShellcheckFailure(_BaseMessage):
    """
    This issue is raised when `shellcheck` is enabled but could not
    run successfully (something went wrong).
    """

    kind = "hint"
    identifier = "R-043"
    message = "There have been errors while scanning with shellcheck."


@dataclass(kw_only=True)
class RecipeLicenseSPDX(_BaseMessage):
    """
    The `license` field must be a valid SPDX identifier.

    See list at [`licenses.txt`](https://github.com/conda-forge/conda-smithy/blob/main/conda_smithy/linter/licenses.txt).
    """

    kind = "hint"
    identifier = "R-044"
    message = (
        "License is not an SPDX identifier (or a custom LicenseRef) "
        "nor an SPDX license expression.\n\n"
        "Documentation on acceptable licenses can be found "
        "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
    )


@dataclass(kw_only=True)
class RecipeInvalidLicenseException(_BaseMessage):
    """
    The `license` field may accept some SPDX exception expressions, as controlled
    in [this file](https://github.com/conda-forge/conda-smithy/blob/main/conda_smithy/linter/license_exceptions.txt)
    """

    kind = "hint"
    identifier = "R-045"
    message = (
        "License exception is not an SPDX exception.\n\n"
        "Documentation on acceptable licenses can be found "
        "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
    )


@dataclass(kw_only=True)
class RecipePythonBuildBackendHost(_BaseMessage):
    """
    Build backends in Python packages must be explictly added to `host`.
    """

    kind = "hint"
    identifier = "R-046"
    message = (
        "No valid build backend found for Python recipe for package "
        "`{package_name}` using `pip`. Python recipes using `pip` need to "
        "explicitly specify a build backend in the `host` section. "
        "If your recipe has built with only `pip` in the `host` section "
        "in the past, you likely should add `setuptools` to the `host` "
        "section of your recipe."
    )
    package_name: str


@dataclass(kw_only=True)
class RecipePythonMinPin(_BaseMessage):
    """
    Python packages should depend on certain `>={min_version}` at runtime,
    but build and test against `{min_version}.*`.
    """

    kind = "hint"
    identifier = "R-047"
    message = (
        "`noarch: python` recipes should usually follow the syntax in "
        "our [documentation](https://conda-forge.org/docs/maintainer/knowledge_base/#noarch-python) "
        "for specifying the Python version.\n"
        "{recommendations}\n"
        "- If the package requires a newer Python version than the currently supported minimum "
        "version on `conda-forge`, you can override the `python_min` variable by adding a "
        "Jinja2 `set` statement at the top of your recipe (or using an equivalent `context` "
        "variable for v1 recipes)."
    )
    recommendations: list[tuple[str, str, str, str]]

    def render_attributes(self):
        recommendations = []
        for (
            report_section_name,
            section_desc,
            report_syntax,
            report_entry,
        ) in self.recommendations:
            recommendations.append(
                f"\n   - For the {report_section_name} section of {section_desc}, you "
                f"should usually use the pin {report_syntax} for the {report_entry} entry."
            )
        return {"recommendations": "".join(recommendations)}


@dataclass(kw_only=True)
class RecipeSpaceSeparatedSpecs(_BaseMessage):
    """
    Prefer `name [version [build]]` match spec syntax.
    """

    kind = "hint"
    identifier = "R-048"
    message = (
        "{output} output has some malformed specs:\n"
        "{bad_specs_list}\n"
        "Requirement spec fields should match the syntax `name [version [build]]`"
        "to avoid known issues in conda-build. For example, instead of "
        "`name =version=build`, use `name version.* build`. "
        "There should be no spaces between version operators and versions either: "
        "`python >= 3.8` should be `python >=3.8`."
    )
    output: str
    bad_specs: dict[str, list[str]]

    def render_attributes(self):
        bad_specs_list = []
        for req_type, specs in self.bad_specs.items():
            specs = [f"`{spec}`" for spec in specs]
            bad_specs_list.append(f"- In section {req_type}: {', '.join(specs)}")
        return {"output": self.output, "bad_specs_list": bad_specs_list}


@dataclass(kw_only=True)
class RecipeOsVersion(_BaseMessage):
    """
    Prefer `name [version [build]]` match spec syntax.
    """

    kind = "hint"
    identifier = "R-049"
    message = (
        "The feedstock is lowering the image versions for one or more platforms: {platforms} "
        "(the default is {default}). Unless you are in the very rare case of repackaging binary "
        "artifacts, consider removing these overrides from conda-forge.yml "
        "in the top feedstock directory."
    )
    platforms: dict[str, str]
    default: str


@dataclass(kw_only=True)
class RecipeRattlerBldBat(_BaseMessage):
    """
    `rattler-build` does not use `bld.bat` scripts, but `build.bat`.
    """

    kind = "hint"
    identifier = "R1-003"
    message = (
        "Found `bld.bat` in recipe directory, but this is a recipe v1 "
        "(rattler-build recipe). rattler-build uses `build.bat` instead of `bld.bat` "
        "for Windows builds. Consider renaming `bld.bat` to `build.bat`."
    )


def generate_docs(output_file: str | None = None) -> str:
    if output_file is None:
        # Let's check if we are in a repo or installed
        maybe_repo_root = Path(__file__).parents[2]
        if (maybe_repo_root / "README.md").is_file() and (
            maybe_repo_root / ".git"
        ).is_dir():
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
    by_categories = {}
    for cls in sorted(collect_messages(), key=lambda obj: obj.identifier):
        category_prefix = cls.identifier.split("-")[0]
        by_categories.setdefault(category_prefix, []).append(cls)
    lines.append("Categories:")
    lines.extend(
        [
            f"- [`{category_prefix}`: {CATEGORIES[category_prefix]}](#{category_prefix})"
            for category_prefix in by_categories
        ]
    )
    for category_prefix, messages in by_categories.items():
        lines.append(f"<a id='{category_prefix}'></a>")
        lines.append(f"## `{category_prefix}`: {CATEGORIES[category_prefix]}")
        lines.append("")
        for cls in messages:
            if cls.identifier in identifiers:
                raise ValueError(f"Duplicate identifier: {cls.identifier}.")
            identifiers.add(cls.identifier)
            lines.extend(
                [
                    f"<a id='{cls.identifier}'></a>",
                    f"### `{cls.identifier}`: `{cls.__name__}`",
                    "",
                    "",
                    cleandoc(cls.__doc__),
                    "",
                    (
                        f"<details>\n\n<summary>{cls.kind.title()} message</summary>\n\n"
                        f"```text\n{cls.message}\n```\n\n</details>"
                        if isinstance(cls.message, str)
                        else "_Message generated dynamically. Template not available._"
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
