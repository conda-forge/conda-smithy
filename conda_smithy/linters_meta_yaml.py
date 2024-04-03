import functools
import itertools
import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import (
    List,
    Iterable,
    Mapping,
    Sequence,
    Union,
    get_args,
    Optional,
)

import github
import requests
from conda_build.license_family import ensure_valid_license_family

from conda_smithy.linting_types import Linter, LintsHints
from conda_smithy.utils import get_yaml

if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib


class Section(str, Enum):
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


ListSectionName = Union[Section.SOURCE, Section.OUTPUTS]
"""
The names of all top-level sections in a meta.yaml file that are expected to be lists.
"""


"""
Note that the subsection key lists may not be complete.
"""


class PackageSubsection(str, Enum):
    """
    The names of all subsections in the PACKAGE section in a meta.yaml file.
    """

    NAME = "name"
    VERSION = "version"


class SourceSubsection(str, Enum):
    """
    The names of all subsections in one element of the SOURCE section in a meta.yaml file.
    """

    URL = "url"


class RequirementsSubsection(str, Enum):
    """
    The names of all subsections in the REQUIREMENTS section in a meta.yaml file.
    Note! The order of the subsections dictates the order in the meta.yaml file.
    """

    BUILD = "build"
    HOST = "host"
    RUN = "run"


class TestSubsection(str, Enum):
    """
    The names of all subsections in the TEST section in a meta.yaml file.
    """

    IMPORTS = "imports"
    COMMANDS = "commands"


class OutputSubsection(str, Enum):
    TEST = "test"
    SCRIPT = "script"
    REQUIREMENTS = "requirements"


class AboutSubsection(str, Enum):
    """
    The names of all subsections in the ABOUT section in a meta.yaml file.
    """

    HOME = "home"
    LICENSE = "license"
    LICENSE_FAMILY = "license_family"
    LICENSE_FILE = "license_file"
    SUMMARY = "summary"


class ExtraSubsection(str, Enum):
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

_SELECTOR_PATTERN = re.compile(r"(.+?)\s*(#.*)?\[([^\[\]]+)](?(2).*)$")

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

    github_client: Optional[github.Github] = None
    """
    A GitHub client to use for additional checks.
    This is only used if is_conda_forge is True.
    """

    @property
    def is_staged_recipe(self) -> bool:
        return self.recipe_dir and self.recipe_dir.name != "recipe"


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
) -> List[str]:
    return [section for section in major_sections if section in Section]


def get_dict_section(meta_yaml: dict, name: Section) -> dict:
    """
    Behaves like get_dict_section_or_subsection, but raises a ValueError if the section is expected to be a list.
    :raises ValueError: If you pass a section name that is expected to be a list.
    You should not catch this exception, it is a programming error.
    """
    if name in get_args(ListSectionName):
        raise ValueError(
            f"The section {name} is expected to be a list, not a dictionary. Use get_list_section instead."
        )
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
    :raises TypeError: if the (sub)section in the parent dict does not represent a dictionary
    (has a meaningful error message).
    """
    section = parent.get(name, {})
    if isinstance(section, Mapping):
        return section

    raise TypeError(
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
    :raises TypeError: if the section in the meta_yaml dict does not represent a list, or a dictionary (if allow_single)
    (contains a meaningful error message).
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
    :raises TypeError: if the section in the meta_yaml dict does not represent a list, or a dictionary (if allow_single)
    (contains a meaningful error message).
    """
    section = meta_yaml.get(name, [])
    if allow_single and isinstance(section, Mapping):
        return [section]
    if isinstance(section, Sequence) and not isinstance(section, str):
        return section

    raise TypeError(
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
        if section not in Section:
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
        if test_out.get(OutputSubsection.SCRIPT, "").endswith((".bat", ".sh")):
            has_outputs_test = True
            continue
        no_test_hints.append(
            f"It looks like the '{out.get('name', '???')}' output doesn't have any tests."
        )

    if has_outputs_test:
        return LintsHints(hints=no_test_hints)

    return LintsHints(["The recipe must have some tests."])


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

    return LintsHints(["The recipe license cannot be unknown."])


def is_selector_line(line, allow_platforms=False, allow_keys=set()):
    # Using the same pattern defined in conda-build (metadata.py),
    # we identify selectors.
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
    recipe_dir = extras.recipe_dir

    if not recipe_dir:
        return LintsHints()

    meta_yaml_file = recipe_dir / "meta.yaml"

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

    if build_section.get("number", None) is not None:
        return LintsHints()
    return LintsHints(["The recipe must have a `build/number` section."])


def lint_requirements_order(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #8: The build section should be before the run section in requirements.
    """
    requirements_section = get_dict_section(meta_yaml, Section.REQUIREMENTS)

    seen_requirements = [
        k for k in requirements_section if k in RequirementsSubsection
    ]
    requirements_order_sorted = sorted(
        seen_requirements,
        key=lambda s: [e for e in RequirementsSubsection].index(s),
    )
    if seen_requirements == requirements_order_sorted:
        return LintsHints()

    return LintsHints(
        [
            "The `requirements/` sections should be defined "
            "in the following order: "
            + ", ".join([e for e in RequirementsSubsection])
            + "; instead saw: "
            + ", ".join(seen_requirements)
            + "."
        ]
    )


def lint_files_hash(
    meta_yaml: dict, _extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #9: Files downloaded should have a hash.
    """
    sources_section = get_list_section(meta_yaml, Section.SOURCE)
    lints = []
    for source in sources_section:
        if "url" in source and not ({"sha1", "sha256", "md5"} & source.keys()):
            lints.append(
                "When defining a source/url please add a sha256, sha1 "
                "or md5 checksum (sha256 preferably)."
            )
    return LintsHints(lints)


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
        return LintsHints(
            ['The recipe `license` should not include the word "License".']
        )

    return LintsHints()


def lint_empty_line_at_end_of_file(
    _meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #11: There should be one empty line at the end of the file.
    Note that this linter reads the recipe from disk.
    """
    recipe_dir = extras.recipe_dir

    if not recipe_dir:
        return LintsHints()

    meta_yaml_file = recipe_dir / "meta.yaml"

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
        return LintsHints(
            [
                f"There are {end_empty_lines_count - 1} too many lines.  "
                "There should be one empty line at the end of the "
                "file."
            ]
        )

    return LintsHints(
        [
            "There are too few lines. There should be one empty "
            "line at the end of the file."
        ]
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
        return LintsHints([str(e)])


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
        return LintsHints(["license_file entry is missing, but is required."])

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
        return LintsHints(
            [
                "Recipe name has invalid characters. only lowercase alpha, numeric, "
                "underscores, hyphens and dots allowed"
            ]
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
    # TODO: this is flawed (open issue)
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
    meta_yaml: dict, extras: MetaYamlLintExtras
) -> LintsHints:
    """
    Lint #14-2: Check that the recipe maintainers exist
    """
    extra_section = get_dict_section(meta_yaml, Section.EXTRA)
    maintainers = extra_section.get(ExtraSubsection.RECIPE_MAINTAINERS, [])

    gh = get_github_client()
    results = LintsHints()

    for maintainer in maintainers:
        if "/" in maintainer:
            # It's a team. Checking for existence is expensive. Skip for now.
            continue
        try:
            gh.get_user(maintainer)
        except github.UnknownObjectException as e:
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
    build_reqs = requirements_section.get(RequirementsSubsection.BUILD, [])
    host_reqs = requirements_section.get(RequirementsSubsection.HOST, [])
    run_reqs = requirements_section.get(RequirementsSubsection.RUN, [])

    outputs_section = get_list_section(meta_yaml, Section.OUTPUTS)

    for out in outputs_section:
        _req = out.get(OutputSubsection.REQUIREMENTS, {})
        if isinstance(_req, Mapping):
            build_reqs += _req.get(RequirementsSubsection.BUILD, [])
            host_reqs += _req.get(RequirementsSubsection.HOST, [])
            run_reqs += _req.get(RequirementsSubsection.RUN, [])
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
    maintainers = extra_section.get(ExtraSubsection.RECIPE_MAINTAINERS, [])
    pr_number = os.environ.get("STAGED_RECIPES_PR_NUMBER")

    if not extras.is_staged_recipe or not maintainers or not pr_number:
        return LintsHints()

    results = LintsHints()
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

    LintsHints.lint(
        f"The following maintainers have not yet confirmed that they are willing to be listed here: "
        f"{', '.join(non_participating_maintainers)}. Please ask them to comment on this PR if they are."
    )


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
]

# TODO: get section should raise lints, move enums to other module
# TODO: check if lists are complete
