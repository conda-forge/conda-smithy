import copy
import fnmatch
import functools
import itertools
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import (
    List,
    Iterable,
    Mapping,
    Sequence,
    Union,
    get_args,
    Optional,
    AbstractSet,
    Literal,
)

import license_expression
from conda.exceptions import InvalidVersionSpec
from conda.models.version import VersionOrder

from conda_smithy.config_file_helpers import (
    ConfigFileName,
    read_local_config_file,
    ConfigFileMustBeDictError,
    MultipleConfigFilesError,
)

try:
    from enum import StrEnum
except ImportError:
    from backports.strenum import StrEnum

import github
import requests
from conda_build.license_family import ensure_valid_license_family
from conda_build.metadata import (
    FIELDS as _CONDA_BUILD_FIELDS,
)

from conda_smithy.linting_utils import (
    Linter,
    LintsHints,
    exceptions_lint,
    AutoLintException,
)
from conda_smithy.utils import get_yaml

if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib

FIELDS = copy.deepcopy(_CONDA_BUILD_FIELDS)

# Just in case 'extra' moves into conda_build
if "extra" not in FIELDS.keys():
    FIELDS["extra"] = {}

# additions by conda-forge
FIELDS["extra"]["recipe-maintainers"] = ()
FIELDS["extra"]["feedstock-name"] = ""


class SectionTypeError(TypeError, AutoLintException):
    """
    Raised when a section or subsection in the meta.yaml file has an unexpected type.
    This exception is automatically converted to a lint by lint_recipe._lint and therefore does not need
    to be caught by linters.
    """

    pass


class Section(StrEnum):
    """
    The names of all top-level sections in a meta.yaml file.
    Note! The order of the sections dictates the order in the meta.yaml file (see lint_section_order).
    """

    PACKAGE = "package"
    SOURCE = "source"
    BUILD = "build"
    REQUIREMENTS = "requirements"
    TEST = "test"
    APP = "app"
    OUTPUTS = "outputs"
    ABOUT = "about"
    EXTRA = "extra"


ListSectionName = Literal[Section.SOURCE, Section.OUTPUTS]
"""
Element of LIST_SECTION_NAMES.
"""

LIST_SECTION_NAMES = get_args(ListSectionName)
"""
The names of all top-level sections in a meta.yaml file that are expected to be lists.
"""

"""
Note that the subsection key lists may not be complete.
"""


class PackageSubsection(StrEnum):
    """
    The names of all subsections in the PACKAGE section in a meta.yaml file.
    """

    NAME = "name"
    VERSION = "version"


class SourceSubsection(StrEnum):
    """
    The names of all subsections in one element of the SOURCE section in a meta.yaml file.
    """

    URL = "url"


class BuildSubsection(StrEnum):
    """
    The names of all subsections in the BUILD section in a meta.yaml file.
    """

    NUMBER = "number"
    NOARCH = "noarch"
    SCRIPT = "script"


class RequirementsSubsection(StrEnum):
    """
    The names of all subsections in the REQUIREMENTS section in a meta.yaml file.
    Note! The order of the subsections dictates the order in the meta.yaml file.
    """

    BUILD = "build"
    HOST = "host"
    RUN = "run"


class TestSubsection(StrEnum):
    """
    The names of all subsections in the TEST section in a meta.yaml file.
    """

    IMPORTS = "imports"
    COMMANDS = "commands"


class OutputSubsection(StrEnum):
    NAME = "name"
    TEST = "test"
    REQUIREMENTS = "requirements"


class OutputTestSubsection(StrEnum):
    """
    The names of all subsections in the TEST subsection of the OUTPUT section in a meta.yaml file.
    """

    SCRIPT = "script"


class AboutSubsection(StrEnum):
    """
    The names of all subsections in the ABOUT section in a meta.yaml file.
    """

    HOME = "home"
    LICENSE = "license"
    LICENSE_FAMILY = "license_family"
    LICENSE_FILE = "license_file"
    SUMMARY = "summary"


class ExtraSubsection(StrEnum):
    """
    The names of all subsections in the EXTRA section in a meta.yaml file.
    """

    RECIPE_MAINTAINERS = "recipe-maintainers"


SectionOrSubsection = Union[
    Section,
    PackageSubsection,
    SourceSubsection,
    RequirementsSubsection,
    TestSubsection,
    OutputSubsection,
    AboutSubsection,
    ExtraSubsection,
]

TEST_KEYS = {TestSubsection.IMPORTS, TestSubsection.COMMANDS}
"""
All TestSubsection keys that are recognized as valid tests.
"""

TEST_FILES = ["run_test.py", "run_test.sh", "run_test.bat", "run_test.pl"]
"""
All filenames that are recognized as valid test files (in the recipe directory).
"""

_SELECTOR_PATTERN = re.compile(r"(.+?)\s*(#.*)?\[([^\[\]]+)\](?(2).*)$")
_JINJA_PATTERN = re.compile(r"\s*\{%\s*(set)\s+[^\s]+\s*=\s*[^\s]+\s*%\}")
_JINJA_VARIABLE_PATTERN = re.compile(r"{{(.*?)}}")

_FAMILIES_NEEDING_LICENSE_FILE = ["gpl", "bsd", "mit", "apache", "psf"]


@dataclass
class MetaYamlLintExtras:
    recipe_dir: Optional[Path] = None
    """
    The recipe directory.
    """
    is_conda_forge: bool = False
    """
    True if executing in a conda-forge CI environment.
    This enables some additional linters that are only relevant for certain conda-forge CI checks.
    """

    @property
    def is_staged_recipe(self) -> bool:
        return self.recipe_dir and self.recipe_dir.name != "recipe"

    @property
    def meta_yaml_file(self) -> Path:
        """
        If recipe_dir is None, this returns a path to meta.yaml in the current directory.
        """
        return (self.recipe_dir or Path()) / "meta.yaml"

    def get_config_file_or_empty(self, name: ConfigFileName) -> dict:
        """
        Get the contents of a config file accompanying the recipe.
        If recipe_dir is not set, or the file does not exist, an empty dictionary is returned.
        :name: The name of the config file.
        :raises ConfigFileMustBeDictError if the file read does not represent a dictionary
        :raises MultipleConfigFilesError if multiple conda_build_config.yaml files are found
        """
        if not self.recipe_dir:
            return {}

        try:
            return read_local_config_file(self.recipe_dir, name)
        except FileNotFoundError:
            return {}


def conda_forge_only(
    linter: Linter[MetaYamlLintExtras],
) -> Linter[MetaYamlLintExtras]:
    """
    Decorator to make a linter only run for conda-forge recipes.
    """

    @functools.wraps(linter)
    def new_linter(meta_yaml: dict, extras: MetaYamlLintExtras) -> LintsHints:
        if extras.is_conda_forge:
            return linter(meta_yaml, extras)
        return LintsHints()

    return new_linter


def _remove_unexpected_major_sections(
    major_sections: Iterable[str],
) -> List[Section]:
    return [
        Section(section)
        for section in major_sections
        if section in iter(Section)
    ]


def get_dict_section(meta_yaml: dict, name: Section) -> dict:
    """
    Behaves like get_dict_section_or_subsection, but raises a ValueError if the section is expected to be a list.
    :raises ValueError: If you pass a section name that is expected to be a list.
    You should not catch this exception, it is a programming error.
    :raises SectionTypeError: if the section in the meta_yaml dict does not represent a dictionary
    """
    if name in LIST_SECTION_NAMES:
        raise ValueError(
            f"The section {name} is expected to be a list, not a dictionary. Use get_list_section instead."
        )
    # can raise SectionTypeError
    return get_dict_section_or_subsection(meta_yaml, name)


def get_dict_section_or_subsection(
    parent: dict, name: SectionOrSubsection
) -> dict:
    """
    Extract a (sub)section from the meta.yaml dictionary that is expected to be a dictionary.
    To extract a top-level section, please use get_dict_section to get an additional check that the section is not
    expected to be a list.
    If the section is not present, an empty dictionary is returned.
    :param parent: The parent dictionary to extract from.
    :param name: The name of the (sub)section to extract.
    :raises SectionTypeError: if the (sub)section in the parent dict does not represent a dictionary
    (has a meaningful error message).
    """
    section = parent.get(name, {})
    if isinstance(section, Mapping):
        return section

    raise SectionTypeError(
        f'The "{name}" section was expected to be a dictionary, but '
        f"got a {type(section).__name__}."
    )


def get_list_section(meta_yaml: dict, name: ListSectionName) -> list:
    """
    Extract a top-level section from the meta.yaml dictionary that is expected to be a list.
    There is automatic conversion of a single dictionary to a list with a single element, if this is allowed for
    the section being extracted.
    If the section is not present, an empty list is returned.
    :param meta_yaml: The meta.yaml dictionary.
    :param name: The name of the section to extract.
    :raises SectionTypeError: if the section in the meta_yaml dict does not represent a list, or a dictionary
    (if allow_single) (contains a meaningful error message).
    """
    allow_single = name == Section.SOURCE
    return _get_list_section_internal(meta_yaml, name, allow_single)


def _get_list_section_internal(
    meta_yaml: dict, name: ListSectionName, allow_single=False
) -> list:
    """
    Extract a top-level section from the meta.yaml dictionary that is expected to be a list.
    If the section is not present, an empty list is returned.
    :param meta_yaml: The meta.yaml dictionary.
    :param name: The name of the section to extract.
    :param allow_single: If True, allow a single dictionary (!) instead of a list, which is returned as a list with
    a single element.
    :raises SectionTypeError: if the section in the meta_yaml dict does not represent a list, or a dictionary
    (if allow_single) (contains a meaningful error message).
    """
    section = meta_yaml.get(name, [])
    if allow_single and isinstance(section, Mapping):
        return [section]
    if isinstance(section, Sequence) and not isinstance(section, str):
        return section

    raise SectionTypeError(
        f'The "{name}" section was expected to be a {"dictionary or a " if allow_single else ""}list, but got a '
        f"{type(section).__module__}.{type(section).__name__}."
    )


def lint_no_unexpected_top_level_keys(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #0: Top-level keys should be expected.
    """
    lints = []
    for section in meta_yaml.keys():
        if section not in iter(Section):
            lints.append(f"The top-level meta key {section} is unexpected")
    return LintsHints(lints)


def lint_section_order(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #1: Top-level keys should have a specific order.
    """
    major_sections = _remove_unexpected_major_sections(meta_yaml.keys())

    section_order_sorted = sorted(
        major_sections, key=lambda s: [e for e in Section].index(s)
    )

    if major_sections == section_order_sorted:
        return LintsHints()

    lints = []

    section_order_sorted_quoted = map(lambda s: f"'{s}'", section_order_sorted)
    section_order_sorted_str = ", ".join(section_order_sorted_quoted)
    section_order_sorted_str = "[" + section_order_sorted_str + "]"
    lints.append(
        "The top-level meta keys are in an unexpected order. "
        f"Expecting {section_order_sorted_str}."
    )

    return LintsHints(lints)


def lint_about_contents(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #2: The about section should have a home, license and summary.
    """
    about_section = get_dict_section(meta_yaml, Section.ABOUT)

    lints = []

    for about_item in [
        AboutSubsection.HOME,
        AboutSubsection.LICENSE,
        AboutSubsection.SUMMARY,
    ]:
        if not about_section.get(about_item):
            lints.append(
                f"The {about_item} item is expected in the about section."
            )

    return LintsHints(lints)


def lint_recipe_maintainers(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #3a: The recipe should have some maintainers.
    Lint #3b: Maintainers should be a list
    """
    lints = []
    extra_section = get_dict_section(meta_yaml, Section.EXTRA)

    # 3a
    if not extra_section.get(ExtraSubsection.RECIPE_MAINTAINERS):
        lints.append(
            "The recipe could do with some maintainers listed in "
            "the `extra/recipe-maintainers` section."
        )

    # 3b
    if not (
        isinstance(
            extra_section.get(ExtraSubsection.RECIPE_MAINTAINERS, []), Sequence
        )
        and not isinstance(
            extra_section.get(ExtraSubsection.RECIPE_MAINTAINERS, []), str
        )
    ):
        lints.append("Recipe maintainers should be a json list.")

    return LintsHints(lints)


def lint_recipe_should_have_tests(
    meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #4: The recipe should have some tests.
    """
    test_section = get_dict_section(meta_yaml, Section.TEST)
    outputs_section = get_list_section(meta_yaml, Section.OUTPUTS)
    recipe_dir = extras.recipe_dir

    if any(key in TEST_KEYS for key in test_section):
        return LintsHints()

    a_test_file_exists = recipe_dir is not None and any(
        (recipe_dir / test_file).exists() for test_file in TEST_FILES
    )

    if a_test_file_exists:
        return LintsHints()

    has_outputs_test = False
    no_test_hints = []

    for out in outputs_section or []:
        test_out = get_dict_section_or_subsection(out, OutputSubsection.TEST)
        if any(key in TEST_KEYS for key in test_out):
            has_outputs_test = True
            continue
        if test_out.get(OutputTestSubsection.SCRIPT, "").endswith(
            (".bat", ".sh")
        ):
            has_outputs_test = True
            continue
        no_test_hints.append(
            f"It looks like the '{out.get('name', '???')}' output doesn't have any tests."
        )

    if has_outputs_test:
        return LintsHints(hints=no_test_hints)

    return LintsHints.lint("The recipe must have some tests.")


def lint_license_cannot_be_unknown(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #5: License cannot be 'unknown.'
    """
    about_section = get_dict_section(meta_yaml, Section.ABOUT)
    license_ = about_section.get(AboutSubsection.LICENSE, "").lower()

    if license_ != "unknown":
        return LintsHints()

    return LintsHints.lint("The recipe license cannot be unknown.")


def is_selector_line(
    line: str,
    allow_platforms: bool = False,
    allow_keys: Optional[AbstractSet] = None,
):
    """
    Using the same pattern defined in conda-build (metadata.py),
    we identify selectors.
    """
    allow_keys = allow_keys or set()

    line = line.rstrip()
    if line.lstrip().startswith("#"):
        # Don't bother with comment only lines
        return False
    m = _SELECTOR_PATTERN.match(line)
    if m:
        nouns = {
            w for w in m.group(3).split() if w not in ("not", "and", "or")
        }
        allowed_nouns = (
            {"win", "linux", "osx", "unix"} if allow_platforms else set()
        ) | allow_keys

        if nouns.issubset(allowed_nouns):
            # the selector only contains (a boolean chain of) platform selectors
            # and/or keys from the conda_build_config.yaml
            return False
        else:
            return True
    return False


def selector_lines(lines):
    for i, line in enumerate(lines):
        if is_selector_line(line):
            yield line, i


# noinspection PyPep8Naming
def lint_selectors_should_be_tidy(
    _meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #6: Selectors should be in a tidy form.
    Note that this linter reads the recipe from disk.
    """
    if not extras.recipe_dir:
        return LintsHints()

    meta_yaml_file = extras.meta_yaml_file

    bad_selectors, bad_lines = [], []
    pyXY_selectors_lint, pyXY_lines_lint = [], []
    pyXY_selectors_hint, pyXY_lines_hint = [], []

    # Good selectors look like ".*\s\s#\s[...]"
    good_selectors_pattern = re.compile(r"(.+?)\s{2,}#\s\[(.+)\](?(2).*)$")
    # Look out for py27, py35 selectors; we prefer py==35
    pyXY_selectors_pattern = re.compile(r".+#\s*\[.*?(py\d{2,3}).*\]")

    try:
        with open(meta_yaml_file, "r") as f:
            for selector_line, line_number in selector_lines(f):
                if not good_selectors_pattern.match(selector_line):
                    bad_selectors.append(selector_line)
                    bad_lines.append(line_number)
                pyXY_matches = pyXY_selectors_pattern.match(selector_line)
                if not pyXY_matches:
                    continue
                for pyXY in pyXY_matches.groups():
                    if int(pyXY[2:]) in (27, 34, 35, 36):
                        # py27, py35 and so on are ok up to py36 (included); only warn
                        pyXY_selectors_hint.append(selector_line)
                        pyXY_lines_hint.append(line_number)
                    else:
                        pyXY_selectors_lint.append(selector_line)
                        pyXY_lines_lint.append(line_number)
    except FileNotFoundError:
        return LintsHints()

    lints = []
    hints = []

    if bad_selectors:
        lints.append(
            "Selectors are suggested to take a "
            "``<two spaces>#<one space>[<expression>]`` form."
            f" See lines {bad_lines}"
        )
    if pyXY_selectors_hint:
        hints.append(
            "Old-style Python selectors (py27, py34, py35, py36) are "
            "deprecated. Instead, consider using the int ``py``. For "
            f"example: ``# [py>=36]``. See lines {pyXY_lines_hint}"
        )
    if pyXY_selectors_lint:
        lints.append(
            "Old-style Python selectors (py27, py35, etc) are only available "
            "for Python 2.7, 3.4, 3.5, and 3.6. Please use explicit comparisons "
            "with the integer ``py``, e.g. ``# [py==37]`` or ``# [py>=37]``. "
            f"See lines {pyXY_lines_lint}"
        )

    return LintsHints(lints, hints)


def lint_must_have_build_number(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #7: The build section should have a build number.
    """
    build_section = get_dict_section(meta_yaml, Section.BUILD)

    if build_section.get(BuildSubsection.NUMBER, None) is not None:
        return LintsHints()
    return LintsHints.lint("The recipe must have a `build/number` section.")


def lint_requirements_order(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #8: The build section should be before the run section in requirements.
    """
    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)

    seen_requirements = [
        k for k in requirements_section if k in iter(RequirementsSubsection)
    ]
    requirements_order_sorted = sorted(
        seen_requirements,
        key=lambda s: [e for e in RequirementsSubsection].index(s),
    )
    if seen_requirements == requirements_order_sorted:
        return LintsHints()

    return LintsHints.lint(
        "The `requirements/` sections should be defined "
        "in the following order: "
        + ", ".join([e for e in RequirementsSubsection])
        + "; instead saw: "
        + ", ".join(seen_requirements)
        + "."
    )


def lint_files_hash(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #9: Files downloaded should have a hash.
    """
    sources_section = get_list_section(meta_yaml, Section.SOURCE)
    results = LintsHints()
    for source in sources_section:
        if "url" in source and not ({"sha1", "sha256", "md5"} & source.keys()):
            results.append_lint(
                "When defining a source/url please add a sha256, sha1 "
                "or md5 checksum (sha256 preferably)."
            )
    return results


def lint_license_should_not_include_license(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #10: License should not include the word 'license'.
    """
    about_section = get_dict_section(meta_yaml, Section.ABOUT)
    license_ = about_section.get(AboutSubsection.LICENSE, "").lower()

    if (
        "license" in license_.lower()
        and "unlicense" not in license_.lower()
        and "licenseref" not in license_.lower()
        and "-license" not in license_.lower()
    ):
        return LintsHints.lint(
            'The recipe `license` should not include the word "License".'
        )

    return LintsHints()


def lint_empty_line_at_end_of_file(
    _meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #11: There should be one empty line at the end of the file.
    Note that this linter reads the recipe from disk.
    """
    if not extras.recipe_dir:
        return LintsHints()

    meta_yaml_file = extras.meta_yaml_file

    try:
        with open(meta_yaml_file, "r") as f:
            lines = f.read().split("\n")
    except FileNotFoundError:
        return LintsHints()

    empty_lines = itertools.takewhile(lambda x: x == "", reversed(lines))
    end_empty_lines_count = len(list(empty_lines))

    if end_empty_lines_count == 1:
        return LintsHints()

    if end_empty_lines_count > 1:
        return LintsHints.lint(
            f"There are {end_empty_lines_count - 1} too many lines. "
            "There should be one empty line at the end of the "
            "file."
        )

    return LintsHints.lint(
        "There are too few lines. There should be one empty "
        "line at the end of the file."
    )


def lint_valid_license_family(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #12: License family must be valid (conda-build checks for that)
    """
    try:
        ensure_valid_license_family(meta_yaml)
    except RuntimeError as e:
        return LintsHints.lint(str(e))

    return LintsHints()


def lint_license_file_present(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #12a: License file must be present for certain license families (does conda-build check for that?)
    """
    about_section = get_dict_section(meta_yaml, Section.ABOUT)
    license_ = about_section.get(AboutSubsection.LICENSE, "").lower()
    license_family = about_section.get(
        AboutSubsection.LICENSE_FAMILY, license_
    ).lower()
    license_file = about_section.get(AboutSubsection.LICENSE_FILE, None)

    if not license_file and any(
        f for f in _FAMILIES_NEEDING_LICENSE_FILE if f in license_family
    ):
        return LintsHints.lint(
            "license_file entry is missing, but is required."
        )

    return LintsHints()


def lint_recipe_name_valid(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #13: Check that the recipe name is valid
    """
    package_section = get_dict_section(meta_yaml, Section.PACKAGE)

    recipe_name = package_section.get(PackageSubsection.NAME, "").strip()
    if re.match(r"^[a-z0-9_\-.]+$", recipe_name) is None:
        return LintsHints.lint(
            "Recipe name has invalid characters. only lowercase alpha, numeric, "
            "underscores, hyphens and dots allowed"
        )

    return LintsHints()


def get_github_client() -> github.Github:
    return github.Github(os.environ["GH_TOKEN"])


@conda_forge_only
def lint_recipe_is_new(
    meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #14-1: Check that the recipe does not already exist in conda-forge or bioconda (only for staged recipes)
    """
    package_section = get_dict_section(meta_yaml, Section.PACKAGE)
    sources_section = get_list_section(meta_yaml, Section.SOURCE)
    recipe_name = package_section.get(PackageSubsection.NAME, "").strip()

    if not extras.is_staged_recipe or not recipe_name:
        return LintsHints()

    results = LintsHints()
    gh = get_github_client()

    conda_forge_org = gh.get_user(os.getenv("GH_ORG", "conda-forge"))
    existing_recipe: Optional[str] = None

    for name in {
        recipe_name,
        recipe_name.replace("-", "_"),
        recipe_name.replace("_", "-"),
    }:
        try:
            if conda_forge_org.get_repo(f"{name}-feedstock"):
                existing_recipe = name
                break
        except github.UnknownObjectException:
            pass

    if existing_recipe and existing_recipe == recipe_name:
        results.append_lint(
            "Feedstock with the same name exists in conda-forge."
        )
    elif existing_recipe:
        results.append_hint(
            f"Feedstock with the name {existing_recipe} exists in conda-forge. "
            f"Is it the same as this package ({recipe_name})?"
        )

    bio = gh.get_user("bioconda").get_repo("bioconda-recipes")
    try:
        bio.get_dir_contents(f"recipes/{recipe_name}")
    except github.UnknownObjectException:
        pass
    else:
        results.append_hint(
            "Recipe with the same name exists in bioconda: "
            "please discuss with @conda-forge/bioconda-recipes."
        )

    url = None
    for source_section in sources_section:
        if str(source_section.get("url")).startswith(
            "https://pypi.io/packages/source/"
        ):
            url = source_section["url"]

    if not url:
        return results

    # get pypi name from  urls like "https://pypi.io/packages/source/b/build/build-0.4.0.tar.gz"
    pypi_name = url.split("/")[6]
    mapping_request = requests.get(
        "https://raw.githubusercontent.com/regro/cf-graph-countyfair/master/mappings/pypi/name_mapping.yaml"
    )

    if mapping_request.status_code != 200:
        return results

    mapping_raw_yaml = mapping_request.content
    mapping = get_yaml().load(mapping_raw_yaml)
    for pkg in mapping:
        if pkg.get("pypi_name", "") == pypi_name:
            conda_name = pkg["conda_name"]
            results.append_hint(
                f"A conda package with same name ({conda_name}) already exists."
            )

    return results


@conda_forge_only
def lint_recipe_maintainers_exist(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #14-2: Check that the recipe maintainers exist
    """
    extra_section = get_dict_section(meta_yaml, Section.EXTRA)
    maintainers = extra_section.get(ExtraSubsection.RECIPE_MAINTAINERS) or []

    gh = get_github_client()
    results = LintsHints()

    for maintainer in maintainers:
        if "/" in maintainer:
            # It's a team. Checking for existence is expensive. Skip for now.
            continue
        try:
            gh.get_user(maintainer)
        except github.UnknownObjectException:
            results.append_lint(
                f'Recipe maintainer "{maintainer}" does not exist'
            )

    return results


@conda_forge_only
def lint_recipe_dir_inside_example_dir(
    _meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #14-3: if the recipe directory is inside the example directory
    """
    recipe_dir = extras.recipe_dir

    if recipe_dir and "recipes/example/" in str(recipe_dir):
        return LintsHints.lint(
            "Please move the recipe out of the example dir and "
            "into its own dir."
        )

    return LintsHints()


@conda_forge_only
def lint_deleted_example_recipe(
    _meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint 14-4: Do not delete example recipe
    """
    recipe_dir = extras.recipe_dir
    if not extras.is_staged_recipe or not recipe_dir:
        return LintsHints()

    example_meta_file = recipe_dir / ".." / "example" / "meta.yaml"

    if example_meta_file.exists():
        return LintsHints()

    return LintsHints.lint(
        "Please do not delete the example recipe found in "
        "`recipes/example/meta.yaml`."
    )


@conda_forge_only
def lint_package_specific_requirements(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #14-5: Package-specific hints (e.g. do not depend on matplotlib, only matplotlib-base)
    """
    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)
    build_reqs = requirements_section.get(RequirementsSubsection.BUILD) or []
    host_reqs = requirements_section.get(RequirementsSubsection.HOST) or []
    run_reqs = requirements_section.get(RequirementsSubsection.RUN) or []

    outputs_section = get_list_section(meta_yaml, Section.OUTPUTS)

    for out in outputs_section:
        _req = out.get(OutputSubsection.REQUIREMENTS, {})
        if isinstance(_req, Mapping):
            build_reqs += _req.get(RequirementsSubsection.BUILD) or []
            host_reqs += _req.get(RequirementsSubsection.HOST) or []
            run_reqs += _req.get(RequirementsSubsection.RUN) or []
        else:
            run_reqs += _req

    hints_toml_url = "https://raw.githubusercontent.com/conda-forge/conda-forge-pinning-feedstock/main/recipe/linter_hints/hints.toml"
    hints_toml_req = requests.get(hints_toml_url)
    if hints_toml_req.status_code != 200:
        # too bad, but not important enough to throw an error;
        # linter will rerun on the next commit anyway
        return LintsHints()

    results = LintsHints()

    hints_toml_str = hints_toml_req.content.decode("utf-8")
    specific_hints = tomllib.loads(hints_toml_str)["hints"]

    for rq in build_reqs + host_reqs + run_reqs:
        dep = rq.split(" ")[0].strip()
        if dep in specific_hints:
            results.append_hint(specific_hints[dep])

    return results


@conda_forge_only
def lint_all_maintainers_have_commented(
    meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #14-6: Check if all listed maintainers have commented
    """
    extra_section = get_dict_section(meta_yaml, Section.EXTRA)
    maintainers = extra_section.get(ExtraSubsection.RECIPE_MAINTAINERS) or []
    pr_number = os.environ.get("STAGED_RECIPES_PR_NUMBER")

    if not extras.is_staged_recipe or not maintainers or not pr_number:
        return LintsHints()

    gh = get_github_client()

    # Get PR details using GitHub API
    current_pr = gh.get_repo("conda-forge/staged-recipes").get_pull(
        int(pr_number)
    )

    # Get PR author, issue comments, and review comments
    pr_author = current_pr.user.login
    issue_comments = current_pr.get_issue_comments()
    review_comments = current_pr.get_reviews()

    # Combine commenters from both issue comments and review comments
    commenters = {comment.user.login for comment in issue_comments}
    commenters.update({review.user.login for review in review_comments})

    # Check if all maintainers have either commented or are the PR author
    non_participating_maintainers = set()
    for maintainer in maintainers:
        if maintainer not in commenters and maintainer != pr_author:
            non_participating_maintainers.add(maintainer)

    if not non_participating_maintainers:
        return LintsHints()

    return LintsHints.lint(
        f"The following maintainers have not yet confirmed that they are willing to be listed here: "
        f"{', '.join(non_participating_maintainers)}. Please ask them to comment on this PR if they are."
    )


def lint_legacy_patterns(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #15: Check if we are using legacy patterns (i.e. pinned numpy packages)
    """
    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)

    build_reqs = requirements_section.get(RequirementsSubsection.BUILD)
    if not build_reqs or ("numpy x.x" not in build_reqs):
        return LintsHints()

    return LintsHints.lint(
        "Using pinned numpy packages is a deprecated pattern.  Consider "
        "using the method outlined "
        "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy)."
    )


def _helper_validate_subsections(
    section_name: str, subsections: Iterable[str]
) -> LintsHints:
    expected_subsections = FIELDS.get(section_name, [])

    if not expected_subsections:
        # we don't know anything about this section, so we deem it valid
        return LintsHints()

    result = LintsHints()
    for subsection in subsections:
        if subsection not in expected_subsections:
            result.append_lint(
                f"The {section_name} section contained an unexpected "
                f"subsection name. {subsection} is not a valid subsection name."
            )

    return result


def lint_subheaders_in_allowed_subheadings(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #16: Subheaders should be in the allowed subheadings
    """
    results = LintsHints()
    major_sections = _remove_unexpected_major_sections(meta_yaml.keys())

    for section in major_sections:
        expected_subsections = FIELDS.get(section, [])
        if not expected_subsections:
            continue
        if section in LIST_SECTION_NAMES:
            for section_element in get_list_section(meta_yaml, section):
                results += _helper_validate_subsections(
                    section, section_element.keys()
                )
            continue
        subsections = get_dict_section(meta_yaml, section).keys()
        results += _helper_validate_subsections(section, subsections)

    return results


def lint_validate_noarch_value(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #17: Validate noarch value
    """
    build_section = get_dict_section(meta_yaml, Section.BUILD)
    noarch_value = build_section.get(BuildSubsection.NOARCH)

    valid_noarch_values = ["python", "generic"]

    if noarch_value is None or noarch_value in valid_noarch_values:
        return LintsHints()

    valid_noarch_str = "`, `".join(valid_noarch_values)
    return LintsHints.lint(
        f"Invalid `noarch` value `{noarch_value}`. Should be one of `{valid_noarch_str}`."
    )


@exceptions_lint(ConfigFileMustBeDictError, MultipleConfigFilesError)
def lint_no_noarch_for_runtime_selectors(
    meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #18: noarch doesn't work with selectors for runtime dependencies
    """
    build_section = get_dict_section(meta_yaml, Section.BUILD)
    noarch_value = build_section.get(BuildSubsection.NOARCH)

    meta_yaml_file = extras.meta_yaml_file

    if noarch_value is None or not meta_yaml_file.exists():
        return LintsHints()

    # this can raise ConfigFileMustBeDictError or MultipleConfigFilesError
    forge_yaml = extras.get_config_file_or_empty(
        ConfigFileName.CONDA_FORGE_YML
    )
    conda_build_config_keys = extras.get_config_file_or_empty(
        ConfigFileName.CONDA_BUILD_CONFIG
    ).keys()

    noarch_platforms = len(forge_yaml.get("noarch_platforms", [])) > 1

    with open(meta_yaml_file, "r") as f:
        in_run_requirements = False
        for line in f:
            line_s = line.strip()
            if line_s == "host:" or line_s == "run:":
                in_run_requirements = True
                run_requirements_spacing = line[: -len(line.lstrip())]
                continue
            if line_s.startswith("skip:") and is_selector_line(line):
                return LintsHints.lint(
                    "`noarch` packages can't have skips with selectors. If "
                    "the selectors are necessary, please remove "
                    "`noarch: {}`.".format(noarch_value)
                )
            if in_run_requirements:
                if run_requirements_spacing == line[: -len(line.lstrip())]:
                    in_run_requirements = False
                    continue
                if is_selector_line(
                    line,
                    allow_platforms=noarch_platforms,
                    allow_keys=conda_build_config_keys,
                ):
                    return LintsHints.lint(
                        "`noarch` packages can't have selectors. If "
                        "the selectors are necessary, please remove "
                        "`noarch: {}`.".format(noarch_value)
                    )

    return LintsHints()


def lint_check_version(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #19: check that the version is conforming to the conda specification
    """
    package_section = get_dict_section(meta_yaml, Section.PACKAGE)
    version = package_section.get(PackageSubsection.VERSION)

    if version is None:
        return LintsHints()

    try:
        VersionOrder(str(version))
    except InvalidVersionSpec as e:
        return LintsHints.lint(
            f"Package version {version} doesn't match conda spec: {e}"
        )

    return LintsHints()


def is_jinja_line(line):
    line = line.rstrip()
    m = _JINJA_PATTERN.match(line)
    if m:
        return True
    return False


def jinja_lines(lines):
    for i, line in enumerate(lines):
        if is_jinja_line(line):
            yield line, i


def lint_nice_jinja2_variables(
    _meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #20: Jinja2 variable definitions should be nice.
    """
    meta_yaml_file = extras.meta_yaml_file

    if extras.recipe_dir is None or not meta_yaml_file.exists():
        return LintsHints()

    bad_jinja = []
    bad_lines = []
    # Good Jinja2 variable definitions look like "{% set .+ = .+ %}"
    good_jinja_pat = re.compile(r"\s*\{%\s(set)\s[^\s]+\s=\s[^\s]+\s%\}")
    with open(meta_yaml_file, "r") as f:
        for jinja_line, line_number in jinja_lines(f):
            if not good_jinja_pat.match(jinja_line):
                bad_jinja.append(jinja_line)
                bad_lines.append(line_number)

    if not bad_jinja:
        return LintsHints()

    return LintsHints.lint(
        "Jinja2 variable definitions are suggested to "
        "take a ``{%<one space>set<one space>"
        "<variable name><one space>=<one space>"
        "<expression><one space>%}`` form. See lines "
        f"{bad_lines}"
    )


def lint_legacy_compiler_usage(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #21: Legacy usage of compilers
    """
    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)
    build_reqs = requirements_section.get(RequirementsSubsection.BUILD) or []

    if not build_reqs or "toolchain" not in build_reqs:
        return LintsHints()

    return LintsHints.lint(
        "Using toolchain directly in this manner is deprecated. Consider "
        "using the compilers outlined "
        "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers)."
    )


def lint_single_space_pinned_requirements(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #22: Single space in pinned requirements
    """
    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)

    results = LintsHints()

    for section, requirements in requirements_section.items():
        for requirement in requirements or []:
            req, _, _ = requirement.partition("#")
            if "{{" in req:
                continue
            parts = req.split()
            if len(parts) > 2 and parts[1] in [
                "!=",
                "=",
                "==",
                ">",
                "<",
                "<=",
                ">=",
            ]:
                # check for too many spaces
                name = parts[0]
                pin = "".join(parts[1:])
                results.append_lint(
                    (
                        f"``requirements: {section}: {requirement}`` should not "
                        f"contain a space between relational operator and the version, i.e. "
                        f"``{name} {pin}``"
                    )
                )
                continue
            # check that there is a space if there is a pin
            bad_char_idx = [(parts[0].find(c), c) for c in "><="]
            bad_char_idx = [bci for bci in bad_char_idx if bci[0] >= 0]
            if bad_char_idx:
                bad_char_idx.sort()
                i = bad_char_idx[0][0]

                name = parts[0][:i]
                pin = parts[0][i:] + "".join(parts[1:])

                results.append_lint(
                    f"``requirements: {section}: {requirement}`` must "
                    "contain a space between the name and the pin, i.e. "
                    f"``{name} {pin}``"
                )
                continue

    return results


def lint_language_version_constraints_noarch_only(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #23: non-noarch builds shouldn't use version constraints on python and r-base
    """
    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)
    outputs_section = get_list_section(meta_yaml, Section.OUTPUTS)
    build_section = get_dict_section(meta_yaml, Section.BUILD)

    noarch_value = build_section.get(BuildSubsection.NOARCH)

    check_languages = ["python", "r-base"]
    host_reqs = requirements_section.get(RequirementsSubsection.HOST) or []
    run_reqs = requirements_section.get(RequirementsSubsection.RUN) or []

    if noarch_value is not None or outputs_section:
        return LintsHints()

    results = LintsHints()

    for language in check_languages:
        filtered_host_reqs = [
            req for req in host_reqs if req.partition(" ")[0] == language
        ]
        filtered_run_reqs = [
            req for req in run_reqs if req.partition(" ")[0] == language
        ]
        if filtered_host_reqs and not filtered_run_reqs:
            results.append_lint(
                f"If {language} is a host requirement, it should be a run requirement."
            )
        for reqs in [filtered_host_reqs, filtered_run_reqs]:
            if language in reqs:
                # no version constraint
                continue
            for req in reqs:
                constraint = req.split(" ", 1)[1]
                if constraint.startswith(">") or constraint.startswith("<"):
                    results.append_lint(
                        f"Non-noarch packages should have {language} requirement without any version constraints."
                    )

    return results


def lint_lint_jinja_variable_references(
    _meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #24: jinja2 variable references should be {{<one space>var<one space>}}
    """
    meta_yaml_file = extras.meta_yaml_file

    if extras.recipe_dir is None or not meta_yaml_file.exists():
        return LintsHints()

    bad_vars = []
    bad_lines = []
    with open(meta_yaml_file, "r") as f:
        for i, line in enumerate(f.readlines()):
            for m in _JINJA_VARIABLE_PATTERN.finditer(line):
                if m.group(1) is None:
                    continue
                var = m.group(1)
                if var != " %s " % var.strip():
                    bad_vars.append(m.group(1).strip())
                    bad_lines.append(i + 1)

    if not bad_vars:
        return LintsHints()

    # This is a hint, sic
    return LintsHints.hint(
        "Jinja2 variable references are suggested to "
        "take a ``{{<one space><variable name><one space>}}``"
        f" form. See lines {bad_lines}."
    )


def lint_require_python_lower_bound(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #25: require a lower bound on python version
    """
    build_section = get_dict_section(meta_yaml, Section.BUILD)
    outputs_section = get_list_section(meta_yaml, Section.OUTPUTS)
    noarch_value = build_section.get(BuildSubsection.NOARCH)

    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)
    run_reqs = requirements_section.get(RequirementsSubsection.RUN) or []

    if noarch_value != "python" or outputs_section:
        return LintsHints()

    for req in run_reqs:
        if (req.strip().split()[0] == "python") and (req != "python"):
            return LintsHints()

    return LintsHints.lint(
        "noarch: python recipes are required to have a lower bound "
        "on the python version. Typically this means putting "
        "`python >=3.6` in **both** `host` and `run` but you should check "
        "upstream for the package's Python compatibility."
    )


def lint_pin_subpackage_pin_compatible(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #26: pin_subpackage is for subpackages and pin_compatible is for non-subpackages of the recipe.
    Contact @carterbox for troubleshooting with this lint.
    """
    outputs_section = get_list_section(meta_yaml, Section.OUTPUTS)
    package_section = get_dict_section(meta_yaml, Section.PACKAGE)

    subpackage_names = []
    for out in outputs_section:
        if OutputSubsection.NAME in out:
            subpackage_names.append(out[OutputSubsection.NAME])  # explicit
    if PackageSubsection.NAME in package_section:
        subpackage_names.append(
            package_section[PackageSubsection.NAME]
        )  # implicit

    results = LintsHints()

    def check_pins(pinning_section: Optional[Iterable[str]]):
        if pinning_section is None:
            return
        for pin in fnmatch.filter(pinning_section, "compatible_pin*"):
            if pin.split()[1] in subpackage_names:
                results.append_lint(
                    "pin_subpackage should be used instead of"
                    f" pin_compatible for `{pin.split()[1]}`"
                    " because it is one of the known outputs of this recipe:"
                    f" {subpackage_names}."
                )
        for pin in fnmatch.filter(pinning_section, "subpackage_pin*"):
            if pin.split()[1] not in subpackage_names:
                results.append_lint(
                    "pin_compatible should be used instead of"
                    f" pin_subpackage for `{pin.split()[1]}`"
                    " because it is not a known output of this recipe:"
                    f" {subpackage_names}."
                )

    def check_pins_build_and_requirements(top_level: dict):
        if "build" in top_level and "run_exports" in top_level["build"]:
            check_pins(top_level["build"]["run_exports"])
        if "requirements" in top_level and "run" in top_level["requirements"]:
            check_pins(top_level["requirements"]["run"])
        if "requirements" in top_level and "host" in top_level["requirements"]:
            check_pins(top_level["requirements"]["host"])

    check_pins_build_and_requirements(meta_yaml)
    for out in outputs_section:
        check_pins_build_and_requirements(out)

    return results


def lint_suggest_pip(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Hint #1: suggest pip
    """
    build_section = get_dict_section(meta_yaml, Section.BUILD)

    if BuildSubsection.SCRIPT not in build_section:
        return LintsHints()

    scripts = build_section[BuildSubsection.SCRIPT]
    if isinstance(scripts, str):
        scripts = [scripts]
    for script in scripts:
        if "python setup.py install" in script:
            return LintsHints.hint(
                "Whenever possible python packages should use pip. "
                "See https://conda-forge.org/docs/maintainer/adding_pkgs.html#use-pip"
            )

    return LintsHints()


def lint_suggest_python_noarch(
    meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Hint #2: suggest python noarch (skip on feedstocks)
    """
    build_section = get_dict_section(meta_yaml, Section.BUILD)
    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)

    noarch_value = build_section.get(BuildSubsection.NOARCH)
    build_reqs = requirements_section.get(RequirementsSubsection.BUILD) or []

    if (
        noarch_value is not None
        or not build_reqs
        or any("_compiler_stub" in b for b in build_reqs)
        or ("pip" not in build_reqs)
        or (not extras.is_staged_recipe and extras.is_conda_forge)
    ):
        return LintsHints()

    noarch_possible = True

    # For some reason, we assume that meta.yaml is always present
    with open(extras.meta_yaml_file, "r") as f:
        in_run_reqs = False

        for line in f:
            line_s = line.strip()
            if line_s == "host:" or line_s == "run:":
                in_run_reqs = True
                run_reqs_spacing = line[: -len(line.lstrip())]
                continue
            if line_s.startswith("skip:") and is_selector_line(line):
                noarch_possible = False
                break
            if in_run_reqs:
                if run_reqs_spacing == line[: -len(line.lstrip())]:
                    in_run_reqs = False
                    continue
                if is_selector_line(line):
                    noarch_possible = False
                    break

    if not noarch_possible:
        return LintsHints()

    return LintsHints.hint(
        "Whenever possible python packages should use noarch. "
        "See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds"
    )


@exceptions_lint(ConfigFileMustBeDictError, MultipleConfigFilesError)
def lint_suggest_fix_shellcheck(
    _meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Hint #3: suggest fixing all recipe/*.sh shellcheck findings
    """
    recipe_dir = extras.recipe_dir

    if not recipe_dir:
        return LintsHints()

    shell_scripts = recipe_dir.glob("*.sh")

    if not shell_scripts:
        return LintsHints()

    # can raise ConfigFileMustBeDictError or MultipleConfigFilesError
    # can also be empty
    forge_yaml = extras.get_config_file_or_empty(
        ConfigFileName.CONDA_FORGE_YML
    )

    shellcheck_enabled = forge_yaml.get("shellcheck", {}).get("enabled", False)

    if not shellcheck_enabled or not shutil.which("shellcheck"):
        return LintsHints()

    max_shellcheck_lines = 50
    cmd = [
        "shellcheck",
        "--enable=all",
        "--shell=bash",
        # SC2154: var is referenced but not assigned,
        #         see https://github.com/koalaman/shellcheck/wiki/SC2154
        "--exclude=SC2154",
    ]

    shell_scripts_str = []
    for script in shell_scripts:
        shell_scripts_str.append(str(script.resolve()))

    p = subprocess.Popen(
        cmd + shell_scripts_str,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={
            "PATH": os.getenv("PATH")
        },  # exclude other env variables to protect against token leakage
    )
    shellcheck_stdout, _ = p.communicate()

    if p.returncode == 0:
        # All files successfully scanned without issues.
        return LintsHints()

    if p.returncode != 1:
        # Something went wrong.
        return LintsHints.hint(
            "There have been errors while scanning with shellcheck."
        )

    # All files successfully scanned with some issues.
    results = LintsHints()

    findings = (
        shellcheck_stdout.decode(sys.stdout.encoding)
        .replace("\r\n", "\n")
        .splitlines()
    )
    results.append_hint(
        "Whenever possible fix all shellcheck findings ('"
        + " ".join(cmd)
        + " recipe/*.sh -f diff | git apply' helps)"
    )
    results.extend_hints(findings[:max_shellcheck_lines])

    if len(findings) > max_shellcheck_lines:
        results.append_hint(
            "Output restricted, there are '%s' more lines."
            % (len(findings) - max_shellcheck_lines)
        )

    return results


def lint_spdx_license(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Hint #4: Check for SPDX license identifiers
    """
    about_section = get_dict_section(meta_yaml, Section.ABOUT)

    license_ = about_section.get(AboutSubsection.LICENSE, "")
    licensing = license_expression.Licensing()
    parsed_exceptions = []
    try:
        parsed_licenses = []
        parsed_licenses_with_exception = licensing.license_symbols(
            license_.strip(), decompose=False
        )
        for li in parsed_licenses_with_exception:
            if isinstance(li, license_expression.LicenseWithExceptionSymbol):
                parsed_licenses.append(li.license_symbol.key)
                parsed_exceptions.append(li.exception_symbol.key)
            else:
                parsed_licenses.append(li.key)
    except license_expression.ExpressionError:
        parsed_licenses = [license_]

    license_ref_regex = re.compile(r"^LicenseRef[a-zA-Z0-9\-.]*$")
    filtered_licenses = []
    for license_ in parsed_licenses:
        if not license_ref_regex.match(license_):
            filtered_licenses.append(license_)

    licenses_file = Path(__file__).parent / "licenses.txt"
    license_exceptions_file = Path(__file__).parent / "license_exceptions.txt"

    with open(licenses_file, "r") as f:
        expected_licenses = f.readlines()
        expected_licenses = set([li.strip() for li in expected_licenses])
    with open(license_exceptions_file, "r") as f:
        expected_exceptions = f.readlines()
        expected_exceptions = set([li.strip() for li in expected_exceptions])

    results = LintsHints()
    if set(filtered_licenses) - expected_licenses:
        results.append_hint(
            "License is not an SPDX identifier (or a custom LicenseRef) nor an SPDX license expression.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )
    if set(parsed_exceptions) - expected_exceptions:
        results.append_hint(
            "License exception is not an SPDX exception.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )

    return results


_CONDA_FORGE_ONLY_LINTERS: List[Linter[MetaYamlLintExtras]] = [
    lint_recipe_is_new,
    lint_recipe_maintainers_exist,
    lint_recipe_dir_inside_example_dir,
    lint_deleted_example_recipe,
    lint_package_specific_requirements,
    lint_all_maintainers_have_commented,
]

META_YAML_LINTERS: List[Linter[MetaYamlLintExtras]] = [
    lint_no_unexpected_top_level_keys,
    lint_section_order,
    lint_about_contents,
    lint_recipe_maintainers,
    lint_recipe_should_have_tests,
    lint_license_cannot_be_unknown,
    lint_selectors_should_be_tidy,
    lint_must_have_build_number,
    lint_requirements_order,
    lint_files_hash,
    lint_license_should_not_include_license,
    lint_empty_line_at_end_of_file,
    lint_valid_license_family,
    lint_license_file_present,
    lint_recipe_name_valid,
    *_CONDA_FORGE_ONLY_LINTERS,
    lint_legacy_patterns,
    lint_subheaders_in_allowed_subheadings,
    lint_validate_noarch_value,
    lint_no_noarch_for_runtime_selectors,
    lint_check_version,
    lint_nice_jinja2_variables,
    lint_legacy_compiler_usage,
    lint_single_space_pinned_requirements,
    lint_language_version_constraints_noarch_only,
    lint_lint_jinja_variable_references,
    lint_require_python_lower_bound,
    lint_pin_subpackage_pin_compatible,
    lint_suggest_pip,
    lint_suggest_python_noarch,
    lint_suggest_fix_shellcheck,
    lint_spdx_license,
]
