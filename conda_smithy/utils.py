import datetime
import json
import os
import re
import shutil
import tempfile
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Union

import jinja2
import jinja2.sandbox
import ruamel.yaml
from conda_build.api import render as conda_build_render
from conda_build.config import Config
from conda_build.render import MetaData
from rattler_build_conda_compat.render import MetaData as RattlerBuildMetaData

RATTLER_BUILD = "rattler-build"
CONDA_BUILD = "conda-build"
SET_PYTHON_MIN_RE = re.compile(r"{%\s+set\s+python_min\s+=")


def _get_metadata_from_feedstock_dir(
    feedstock_directory: Union[str, os.PathLike],
    forge_config: Dict[str, Any],
    conda_forge_pinning_file: Union[str, os.PathLike, None] = None,
) -> Union[MetaData, RattlerBuildMetaData]:
    """
    Return either the conda-build metadata or rattler-build metadata from the feedstock directory
    based on conda_build_tool value from forge_config.
    Raises OsError if no meta.yaml or recipe.yaml is found in feedstock_directory.
    """
    if forge_config and forge_config.get("conda_build_tool") == RATTLER_BUILD:
        meta = RattlerBuildMetaData(
            feedstock_directory,
        )
    else:
        if conda_forge_pinning_file:
            config = Config(
                variant_config_files=[conda_forge_pinning_file],
            )
        else:
            config = None
        meta = conda_build_render(
            feedstock_directory,
            config=config,
            finalize=False,
            bypass_env_check=True,
            trim_skip=False,
        )[0][0]

    return meta


def get_feedstock_name_from_meta(
    meta: Union[MetaData, RattlerBuildMetaData]
) -> str:
    """Get the feedstock name from a parsed meta.yaml or recipe.yaml."""
    if "feedstock-name" in meta.meta["extra"]:
        return meta.meta["extra"]["feedstock-name"]
    elif "parent_recipe" in meta.meta["extra"]:
        return meta.meta["extra"]["parent_recipe"]["name"]
    else:
        return meta.name()


def get_feedstock_about_from_meta(meta) -> dict:
    """Fetch the feedstock about from the parsed meta.yaml."""
    # it turns out that conda_build would not preserve the feedstock about:
    #   - if a subpackage does not have about, it uses the feedstock's
    #   - if a subpackage has about, it's used as is
    # therefore we need to parse the yaml again just to get the about section...
    if "parent_recipe" in meta.meta["extra"]:
        recipe_meta = os.path.join(
            meta.meta["extra"]["parent_recipe"]["path"], "meta.yaml"
        )
        with open(recipe_meta) as fh:
            content = render_meta_yaml("".join(fh))
            meta = get_yaml().load(content)
        return dict(meta["about"])
    else:
        # no parent recipe for any reason, use self's about
        return dict(meta.meta["about"])


def get_yaml(allow_duplicate_keys: bool = True):
    # define global yaml API
    # roundrip-loader and allowing duplicate keys
    # for handling # [filter] / # [not filter]
    # Don't use a global variable for this as a global
    # variable will make conda-smithy thread unsafe.
    yaml = ruamel.yaml.YAML(typ="rt")
    yaml.allow_duplicate_keys = allow_duplicate_keys
    return yaml


@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp("_recipe")
    yield tmp_dir
    shutil.rmtree(tmp_dir)


class NullUndefined(jinja2.Undefined):
    def __str__(self):
        return self._undefined_name

    def __getattr__(self, name):
        return f"{self}.{name}"

    def __getitem__(self, name):
        return f'{self}["{name}"]'


class MockOS(dict):
    def __init__(self):
        self.environ = defaultdict(lambda: "")
        self.sep = "/"


def stub_compatible_pin(*args, **kwargs):
    return f"compatible_pin {args[0]}"


def stub_subpackage_pin(*args, **kwargs):
    return f"subpackage_pin {args[0]}"


def _munge_python_min(text):
    new_lines = []
    for line in text.splitlines(keepends=True):
        if SET_PYTHON_MIN_RE.match(line):
            line = "{% set python_min = '9999' %}\n"
        new_lines.append(line)
    return "".join(new_lines)


def render_meta_yaml(text):
    env = jinja2.sandbox.SandboxedEnvironment(undefined=NullUndefined)

    # stub out cb3 jinja2 functions - they are not important for linting
    #    if we don't stub them out, the ruamel.yaml load fails to interpret them
    #    we can't just use conda-build's api.render functionality, because it would apply selectors
    env.globals.update(
        dict(
            compiler=lambda x: x + "_compiler_stub",
            stdlib=lambda x: x + "_stdlib_stub",
            pin_subpackage=stub_subpackage_pin,
            pin_compatible=stub_compatible_pin,
            cdt=lambda *args, **kwargs: "cdt_stub",
            load_file_regex=lambda *args, **kwargs: defaultdict(lambda: ""),
            load_file_data=lambda *args, **kwargs: defaultdict(lambda: ""),
            load_setup_py_data=lambda *args, **kwargs: defaultdict(lambda: ""),
            load_str_data=lambda *args, **kwargs: defaultdict(lambda: ""),
            datetime=datetime,
            time=time,
            target_platform="linux-64",
            build_platform="linux-64",
            mpi="mpi",
            python_min="9999",  # use as a sentinel value for linting
        )
    )
    mockos = MockOS()
    py_ver = "3.7"
    context = {"os": mockos, "environ": mockos.environ, "PY_VER": py_ver}
    content = env.from_string(_munge_python_min(text)).render(context)
    return content


@contextmanager
def update_conda_forge_config(forge_yaml):
    """Utility method used to update conda forge configuration files

    Usage:
    >>> with update_conda_forge_config(somepath) as cfg:
    ...     cfg['foo'] = 'bar'
    """
    if os.path.exists(forge_yaml):
        with open(forge_yaml) as fh:
            code = get_yaml().load(fh)
    else:
        code = {}

    # Code could come in as an empty list.
    if not code:
        code = {}

    yield code

    get_yaml().dump(code, Path(forge_yaml))


def merge_dict(src, dest):
    """Recursive merge dictionary"""
    for key, value in src.items():
        if isinstance(value, dict):
            # get node or create one
            node = dest.setdefault(key, {})
            merge_dict(value, node)
        else:
            dest[key] = value

    return dest


def _json_default(obj):
    """Accept sets for JSON"""
    if isinstance(obj, set):
        return sorted(obj)
    else:
        return obj


class HashableDict(dict):
    """Hashable dict so it can be in sets"""

    def __hash__(self):
        return hash(json.dumps(self, sort_keys=True, default=_json_default))
