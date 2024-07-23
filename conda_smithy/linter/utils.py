from collections.abc import Sequence
import copy
from glob import glob
import os
import re
from typing import Mapping

from conda_build.metadata import (
    FIELDS as cbfields,
)

FIELDS = copy.deepcopy(cbfields)

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


def get_section(parent, name, lints):
    if name == "source":
        return get_list_section(parent, name, lints, allow_single=True)
    elif name == "outputs":
        return get_list_section(parent, name, lints)

    section = parent.get(name, {})
    if not isinstance(section, Mapping):
        lints.append(
            'The "{}" section was expected to be a dictionary, but '
            "got a {}.".format(name, type(section).__name__)
        )
        section = {}
    return section


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


def find_local_config_file(recipe_dir, filename):
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
