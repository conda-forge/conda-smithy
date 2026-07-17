from __future__ import annotations

import copy
import os
import re
import time
import tomllib
from collections.abc import Mapping, Sequence
from functools import lru_cache
from glob import glob
from typing import Any, Optional, Union

import requests
from conda.models.version import InvalidVersionSpec, VersionOrder
from conda_build.metadata import (
    FIELDS as _CONDA_BUILD_FIELDS,
)
from rattler_build_conda_compat import loader as rattler_loader
from rattler_build_conda_compat.recipe_sources import get_all_sources
from requests.exceptions import Timeout

from conda_smithy.deprecations import deprecated
from conda_smithy.linter import messages as msg
from conda_smithy.utils import get_yaml

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
    "flit",
    "flit-core",
    "hatchling",
    "poetry",
    "poetry-core",
    "pdm-backend",
    "pdm-pep517",
    "pymsbuild",
    "meson-python",
    "scikit-build-core",
    "sphinx-theme-builder",
    "maturin",
    "jupyter_packaging",
    "whey",
    "uv-build",
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


def get_recipe_v1_section(meta, name) -> Union[dict, list[dict]]:
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


def is_selector_line(
    line, allow_platforms=False, allow_keys=set(), only_in_comment=False
):
    # Using the same pattern defined in conda-build (metadata.py),
    # we identify selectors.
    line = line.rstrip()
    if line.lstrip().startswith("#"):
        # Don't bother with comment only lines
        return False
    m = sel_pat.match(line)
    if m:
        if only_in_comment and not m.group(2):
            return False
        nouns = {w for w in m.group(3).split() if w not in ("not", "and", "or")}
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


def selector_lines(lines, only_in_comment=False):
    for i, line in enumerate(lines):
        if is_selector_line(line, only_in_comment=only_in_comment):
            yield line, i


def jinja_lines(lines):
    for i, line in enumerate(lines):
        if is_jinja_line(line):
            yield line, i


def _lint_recipe_name(recipe_name: str) -> Optional[str]:
    if re.match(r"^[a-z0-9_\-.]+$", recipe_name) is None:
        return msg.r.InvalidPackageName().as_string()

    return None


def _lint_package_version(version: Optional[str]) -> Optional[str]:
    if version is None:
        return msg.r.MissingVersion().as_string()

    ver = str(version)

    if "${{" in ver:
        # version is templatised. skip the lint
        return

    try:
        VersionOrder(ver)
    except InvalidVersionSpec as e:
        return msg.r.InvalidVersion(version=ver, error=str(e)).as_string()


PINNING_FEEDSTOCK_RAW = (
    "https://raw.githubusercontent.com/conda-forge/conda-forge-pinning-feedstock/main"
)


# cache size should be >= number of urls in use; old epochs are never needed again
@lru_cache(maxsize=5)
def _try_fetch_url_content(url: str, epoch_hour: int) -> Optional[str]:
    """private helper for _try_fetch_url_content_cached"""
    try:
        payload = requests.get(url, timeout=5)
    except Timeout:
        return None
    if payload.status_code != 200:
        # too bad, but not important enough to throw an error;
        # linter will rerun on the next commit anyway
        return None
    return payload.content.decode("utf-8")


def _try_fetch_url_content_cached(url: str) -> Optional[str]:
    """self-limited to update only once per hour"""
    epoch_hour = int(time.time() / 3600)  # time.time() is in seconds
    return _try_fetch_url_content(url, epoch_hour)


def load_linter_toml_metadata():
    url = f"{PINNING_FEEDSTOCK_RAW}/recipe/linter_hints/hints.toml"
    if (hints_toml_str := _try_fetch_url_content_cached(url)) is None:
        return None
    return tomllib.loads(hints_toml_str)


@deprecated(
    "2026.7",
    "2026.9",
    addendum="Use `load_linter_toml_metadata` instead.",
)
def load_linter_toml_metdata_internal(time_salt=None):
    return load_linter_toml_metadata()


# BW compat for the (misspelled) public alias
deprecated.constant(
    "2026.7",
    "2026.9",
    "load_linter_toml_metdata",
    load_linter_toml_metadata,
    addendum="Use `load_linter_toml_metadata` instead.",
)


def get_global_pinning_python_min() -> Optional[str]:
    """The default `python_min` from conda-forge's global pinning, as a
    string, or None if it cannot be fetched."""
    url = f"{PINNING_FEEDSTOCK_RAW}/recipe/conda_build_config.yaml"
    if (pinning_yaml := _try_fetch_url_content_cached(url)) is None:
        return None
    python_min = get_yaml().load(pinning_yaml).get("python_min")
    if isinstance(python_min, Sequence) and not isinstance(python_min, str):
        # the first entry is the default; later entries are platform
        # exceptions gated by selector comments (e.g. win-arm64)
        python_min = python_min[0] if python_min else None
    return str(python_min) if python_min is not None else None


def flatten_v1_if_else(requirements: list[str | dict] | str) -> list[str]:
    flattened_requirements = []
    for req in requirements:
        if isinstance(req, dict):
            flattened_requirements.extend(
                flatten_v1_if_else(req["then"])
                if isinstance(req["then"], list)
                else [req["then"]]
            )
            flattened_requirements.extend(
                flatten_v1_if_else(req.get("else", []))
                if isinstance(req.get("else", []), list)
                else [req["else"]]
            )
        else:
            flattened_requirements.append(req)
    return flattened_requirements


def get_all_test_requirements(
    meta: dict, lints: list[str], recipe_version: int
) -> list[str]:
    if recipe_version == 1:
        test_section = get_section(meta, "tests", lints, recipe_version)
        test_reqs = []
        for test_element in test_section:
            test_reqs += (test_element.get("requirements") or {}).get("run") or []

            if "python" in test_element:
                py_version = test_element["python"].get("python_version")

                if isinstance(py_version, str):
                    py_version = [py_version]

                if isinstance(py_version, list):
                    test_reqs += [f"python {pv}" for pv in py_version]
                else:
                    test_reqs.append("python")
    else:
        test_section = get_section(meta, "test", lints, recipe_version)
        test_reqs = test_section.get("requires") or []
    return test_reqs


def get_version_independent(
    build_section: dict[str, Any], language: str, recipe_version: int
) -> bool:
    version_independent = False
    if language == "python":
        if recipe_version == 1:
            version_independent = build_section.get(language, {}).get(
                "version_independent", False
            )
        else:
            version_independent = build_section.get(
                f"{language}_version_independent", False
            )
    return version_independent
