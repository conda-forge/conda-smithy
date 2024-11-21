import copy
import os
import re
import sys
import time
from collections.abc import Sequence
from functools import lru_cache
from glob import glob
from typing import Dict, List, Mapping, Optional, Union

import requests
from conda.models.version import InvalidVersionSpec, VersionOrder
from conda_build.metadata import (
    FIELDS as _CONDA_BUILD_FIELDS,
)
from rattler_build_conda_compat import loader as rattler_loader
from rattler_build_conda_compat.recipe_sources import get_all_sources

if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib

FIELDS = copy.deepcopy(_CONDA_BUILD_FIELDS)

# Just in case 'extra' moves into conda_build
if "extra" not in FIELDS.keys():
    FIELDS["extra"] = {}

FIELDS["extra"]["recipe-maintainers"] = ()
FIELDS["extra"]["feedstock-name"] = ""

EXPECTED_SECTION_ORDER = [
    "package",
    "source",
    "build",
    "requirements",
    "test",
    "app",
    "outputs",
    "about",
    "extra",
]

REQUIREMENTS_ORDER = ["build", "host", "run"]

TEST_KEYS = {"imports", "commands"}
TEST_FILES = ["run_test.py", "run_test.sh", "run_test.bat", "run_test.pl"]


sel_pat = re.compile(r"(.+?)\s*(#.*)?\[([^\[\]]+)\](?(2).*)$")
jinja_pat = re.compile(r"\s*\{%\s*(set)\s+[^\s]+\s*=\s*[^\s]+\s*%\}")
JINJA_VAR_PAT = re.compile(r"{{(.*?)}}")

CONDA_BUILD_TOOL = "conda-build"
RATTLER_BUILD_TOOL = "rattler-build"

VALID_PYTHON_BUILD_BACKENDS = [
    "setuptools",
    "flit-core",
    "hatchling",
    "poetry-core",
    "pdm-backend",
    "pdm-pep517",
    "pymsbuild",
    "meson-python",
    "scikit-build-core",
    "maturin",
    "jupyter_packaging",
    "whey",
]


def get_section(parent, name, lints, recipe_version: int = 0):
    if recipe_version == 0:
        return get_meta_section(parent, name, lints)
    elif recipe_version == 1:
        return get_recipe_v1_section(parent, name)
    else:
        raise ValueError(f"Unknown recipe version: {recipe_version}")


def get_meta_section(parent, name, lints):
    if name == "source":
        return get_list_section(parent, name, lints, allow_single=True)
    elif name == "outputs":
        return get_list_section(parent, name, lints)

    section = parent.get(name, {})
    if not isinstance(section, Mapping):
        lints.append(
            f'The "{name}" section was expected to be a dictionary, but '
            f"got a {type(section).__name__}."
        )
        section = {}
    return section


def get_recipe_v1_section(meta, name) -> Union[Dict, List[Dict]]:
    if name == "requirements":
        return rattler_loader.load_all_requirements(meta)
    elif name == "tests":
        return rattler_loader.load_all_tests(meta)
    elif name == "source":
        sources = get_all_sources(meta)
        return list(sources)

    return meta.get(name, {})


def get_list_section(parent, name, lints, allow_single=False):
    section = parent.get(name, [])
    if allow_single and isinstance(section, Mapping):
        return [section]
    elif isinstance(section, Sequence) and not isinstance(section, str):
        return section
    else:
        msg = 'The "{}" section was expected to be a {}list, but got a {}.{}.'.format(
            name,
            "dictionary or a " if allow_single else "",
            type(section).__module__,
            type(section).__name__,
        )
        lints.append(msg)
        return [{}]


def find_local_config_file(recipe_dir: str, filename: str) -> Optional[str]:
    # support
    # 1. feedstocks
    # 2. staged-recipes with custom conda-forge.yaml in recipe
    # 3. staged-recipes
    found_filesname = (
        glob(os.path.join(recipe_dir, filename))
        or glob(
            os.path.join(recipe_dir, "..", filename),
        )
        or glob(
            os.path.join(recipe_dir, "..", "..", filename),
        )
    )

    return found_filesname[0] if found_filesname else None


def is_selector_line(line, allow_platforms=False, allow_keys=set()):
    # Using the same pattern defined in conda-build (metadata.py),
    # we identify selectors.
    line = line.rstrip()
    if line.lstrip().startswith("#"):
        # Don't bother with comment only lines
        return False
    m = sel_pat.match(line)
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


def is_jinja_line(line):
    line = line.rstrip()
    m = jinja_pat.match(line)
    if m:
        return True
    return False


def selector_lines(lines):
    for i, line in enumerate(lines):
        if is_selector_line(line):
            yield line, i


def jinja_lines(lines):
    for i, line in enumerate(lines):
        if is_jinja_line(line):
            yield line, i


def _lint_recipe_name(recipe_name: str) -> Optional[str]:
    wrong_recipe_name = "Recipe name has invalid characters. only lowercase alpha, numeric, underscores, hyphens and dots allowed"

    if re.match(r"^[a-z0-9_\-.]+$", recipe_name) is None:
        return wrong_recipe_name

    return None


def _lint_package_version(version: Optional[str]) -> Optional[str]:
    no_package_version = "Package version is missing."
    invalid_version = "Package version {ver} doesn't match conda spec: {err}"

    if not version:
        return no_package_version

    ver = str(version)
    try:
        VersionOrder(ver)
    except InvalidVersionSpec as e:
        return invalid_version.format(ver=ver, err=e)


def load_linter_toml_metdata():
    # ensure we refresh the cache every hour
    ttl = 3600
    time_salt = int(time.time() / ttl)
    return load_linter_toml_metdata_internal(time_salt)


@lru_cache(maxsize=1)
def load_linter_toml_metdata_internal(time_salt):
    hints_toml_url = "https://raw.githubusercontent.com/conda-forge/conda-forge-pinning-feedstock/main/recipe/linter_hints/hints.toml"
    hints_toml_req = requests.get(hints_toml_url)
    if hints_toml_req.status_code != 200:
        # too bad, but not important enough to throw an error;
        # linter will rerun on the next commit anyway
        return None
    hints_toml_str = hints_toml_req.content.decode("utf-8")
    return tomllib.loads(hints_toml_str)
