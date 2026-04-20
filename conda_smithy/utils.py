import dataclasses
import datetime
import json
import os
import re
import shutil
import tempfile
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from typing import Any, Optional, Union

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
    forge_config: dict[str, Any],
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
    meta: Union[MetaData, RattlerBuildMetaData],
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
        with open(recipe_meta, encoding="utf-8") as fh:
            content = render_meta_yaml("".join(fh))
            meta = get_yaml().load(content)
        return dict(meta["about"])
    else:
        # no parent recipe for any reason, use self's about
        return dict(meta.meta["about"])


def get_yaml(allow_duplicate_keys: bool = True, preserve_quotes: bool = False):
    # define global yaml API
    # roundrip-loader and allowing duplicate keys
    # for handling # [filter] / # [not filter]
    # Don't use a global variable for this as a global
    # variable will make conda-smithy thread unsafe.
    yaml = ruamel.yaml.YAML(typ="rt")
    yaml.allow_duplicate_keys = allow_duplicate_keys
    yaml.preserve_quotes = preserve_quotes
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
        self.environ = defaultdict(str)
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
            cdt=lambda x: x.replace("-", "_") + "_cdt_stub",
            load_file_regex=lambda *args, **kwargs: defaultdict(str),
            load_file_data=lambda *args, **kwargs: defaultdict(str),
            load_setup_py_data=lambda *args, **kwargs: defaultdict(str),
            load_str_data=lambda *args, **kwargs: defaultdict(str),
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
        with open(forge_yaml, encoding="utf-8") as fh:
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


def file_permissions(path) -> str:
    return oct(os.stat(path).st_mode & 0o777)


class HashableDict(dict):
    """Hashable dict so it can be in sets"""

    def __hash__(self):
        return hash(json.dumps(self, sort_keys=True, default=_json_default))


def ensure_standard_strings(cfg: Any) -> Any:
    """Ensure an object composed of sequences, dicts, and values only has
    Python `str` strings in it."""

    if isinstance(cfg, str):
        return str(cfg)
    elif isinstance(cfg, Mapping):
        for k in list(cfg.keys()):
            v = cfg.pop(k)
            k = ensure_standard_strings(k)
            v = ensure_standard_strings(v)
            cfg[k] = v
        return cfg
    elif isinstance(cfg, Sequence):
        return type(cfg)([ensure_standard_strings(v) for v in cfg])
    else:
        return cfg


@dataclasses.dataclass
class ConditionalValue:
    value: Any
    os: Optional[list[str]] = None
    platform: Optional[list[str]] = None
    provider: Optional[list[str]] = None

    def __str__(self) -> str:
        return str({k: v for k, v in dataclasses.asdict(self).items() if v is not None})


def filter_conditional_values(
    value: Any,
    os: Optional[str] = None,
    platform: Optional[str] = None,
    provider: Optional[str] = None,
) -> list[ConditionalValue]:
    """
    Filter "conditional values" as found in `workflow_settings` by specified
    criteria, and return a list normalized to `ConditionalValue` instances.

    The `value` is the value corresponding to a `workflow_settings` key. It may
    be:

    - A list of "conditional value" dicts, such as the value of
      `store_build_artifacts` in:

      ```yaml
      workflow_settings:
        store_build_artifacts:
          - provider: github_actions
            value: true
          - platform: [win_64, linux_64]  # matched as OR
            value: true
      ```

      All items that matched the criteria will be returned, normalized to
      `ConditionalValue` instances. Normally, you'd want to use the ultimate
      value from the list. If no items matched, an empty list will be returned.

    - A direct value, as from `store_build_artifacts: true`. In that case, a
      list with a single `ConditionalValue` instance will be returned.

    - A `None`, i.e. when there is no `store_build_artifacts` key. In that case,
      an empty list will be returned.
    """

    # If None is passed, there is no value. Return an empty list.
    if value is None:
        return []

    # If value is not a list, then a value has been assigned to the key
    # directly. Wrap it in `ConditionalValue` and return as the only item.
    if not isinstance(value, list):
        return [ConditionalValue(value=value)]

    # Otherwise, it's a list of "conditional values". Filter them using
    # specified criteria.

    criteria = {
        "os": os,
        "platform": platform.replace("-", "_") if platform else None,
        "provider": provider,
    }
    ret = []
    for value_item in value:
        ret_item = {"value": value_item["value"]}
        for criteria_key, needle in criteria.items():
            if criteria_key in value_item:
                haystack: Union[list[str], str] = value_item.get(criteria_key, [needle])
                # Normalize the condition into a list.
                if not isinstance(haystack, list):
                    haystack = [haystack]
                ret_item[criteria_key] = haystack
                # Filter by it if requested.
                if needle is not None and needle not in haystack:
                    break
        else:
            ret.append(ConditionalValue(**ret_item))
    return ret


def get_workflow_settings(
    workflow_settings: dict[str, Any], provider: str, platform: str
) -> dict[str, Any]:
    """
    Process the `workflow_settings` dictionary, returning the keys and specific
    values for given provider and platform.
    """

    os = platform.split("-", 1)[0]
    data = {}
    for setting_key, setting_value in workflow_settings.items():
        filtered = filter_conditional_values(
            setting_value,
            provider=provider,
            platform=platform,
            os=os,
        )
        if len(filtered) > 1:
            raise ValueError(
                f"More than one value matched for `workflow_settings."
                f"{setting_key}` when provider={provider} and "
                f"platform={platform}: {filtered[0]} vs. {filtered[1]}"
            )
        data[setting_key] = filtered[-1].value if filtered else None

    for path_var in ("tools_install_dir", "build_workspace_dir"):
        if data[path_var] is None:
            continue
        win_path = PureWindowsPath(data[path_var])
        print((os, win_path, win_path.drive))
        if os == "win":
            if not win_path.drive:
                raise ValueError(
                    f"workflow_settings.{path_var} specifies non-Windows path "
                    f"for Windows workflows: {win_path}"
                )
        elif win_path.drive:
            raise ValueError(
                f"workflow_settings.{path_var} specifies Windows path for Unix "
                f"workflows: {win_path}"
            )

    return data


def fill_workflow_settings_defaults(
    workflow_settings: dict[str, Any],
    provider: str,
    platform: str,
    gha_runs_on: list[str],
) -> None:
    """
    Fill the missing entries from `workflow_settings` with defaults for
    the given provider-platform combination.
    """
    os = platform.split("-", 1)[0]
    if workflow_settings.get("tools_install_dir") is None:
        win_default = (
            r"D:\Miniforge" if "windows-latest" in gha_runs_on else r"C:\Miniforge"
        )
        workflow_settings["tools_install_dir"] = (
            win_default if os == "win" else "~/miniforge3"
        )
    if workflow_settings.get("build_workspace_dir") is None:
        tools_drive = (
            PureWindowsPath(workflow_settings["tools_install_dir"]).drive
            if os == "win"
            else ""
        )
        workflow_settings["build_workspace_dir"] = {
            "linux": "build_artifacts",
            "osx": f"{workflow_settings['tools_install_dir']}/conda-bld",
            "win": rf"{tools_drive}\\bld\\",
        }[os]
