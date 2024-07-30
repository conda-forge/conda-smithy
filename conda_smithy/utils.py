import datetime
import json
import logging
import os
import shutil
import tempfile
import time
import warnings
from collections import defaultdict
from contextlib import contextmanager
from itertools import chain
from pathlib import Path
from typing import Any, Dict, Union

import conda_build
import conda_build.utils
import jinja2
import jinja2.sandbox
import ruamel.yaml
import yaml
from conda.models.match_spec import MatchSpec
from conda_build.api import render as conda_build_render
from conda_build.render import MetaData
from rattler_build_conda_compat.render import MetaData as RattlerBuildMetaData

from conda_smithy.feedstock_io import remove_file_or_dir
from conda_smithy.validate_schema import (
    CONDA_FORGE_YAML_DEFAULTS_FILE,
    validate_json_schema,
)

RATTLER_BUILD = "rattler-build"
CONDA_BUILD = "conda-build"

logger = logging.getLogger(__name__)


def _update_dict_within_dict(items, config):
    """recursively update dict within dict, if any"""
    for key, value in items:
        if isinstance(value, dict):
            config[key] = _update_dict_within_dict(
                value.items(), config.get(key, {})
            )
        else:
            config[key] = value
    return config


def _santize_remote_ci_setup(remote_ci_setup):
    remote_ci_setup_ = conda_build.utils.ensure_list(remote_ci_setup)
    remote_ci_setup = []
    for package in remote_ci_setup_:
        if package.startswith(("'", '"')):
            pass
        elif ("<" in package) or (">" in package) or ("|" in package):
            package = '"' + package + '"'
        remote_ci_setup.append(package)
    return remote_ci_setup


def _read_forge_config(forge_dir, forge_yml=None):
    # Load default values from the conda-forge.yml file
    with open(CONDA_FORGE_YAML_DEFAULTS_FILE) as fh:
        default_config = yaml.safe_load(fh.read())

    if forge_yml is None:
        forge_yml = os.path.join(forge_dir, "conda-forge.yml")

    if not os.path.exists(forge_yml):
        raise RuntimeError(
            f"Could not find config file {forge_yml}."
            " Either you are not rerendering inside the feedstock root (likely)"
            " or there's no `conda-forge.yml` in the feedstock root (unlikely)."
            " Add an empty `conda-forge.yml` file in"
            " feedstock root if it's the latter."
        )

    with open(forge_yml) as fh:
        documents = list(yaml.safe_load_all(fh))
        file_config = (documents or [None])[0] or {}

    # Validate loaded configuration against a JSON schema.
    validate_lints, validate_hints = validate_json_schema(file_config)
    for err in chain(validate_lints, validate_hints):
        logger.warning(
            "%s: %s = %s -> %s",
            os.path.relpath(forge_yml, forge_dir),
            err.json_path,
            err.instance,
            err.message,
        )
        logger.debug("Relevant schema:\n%s", json.dumps(err.schema, indent=2))

    # The config is just the union of the defaults, and the overridden
    # values.
    config = _update_dict_within_dict(file_config.items(), default_config)

    # check for conda-smithy 2.x matrix which we can't auto-migrate
    # to conda_build_config
    if file_config.get("matrix") and not os.path.exists(
        os.path.join(
            forge_dir, config["recipe_dir"], "conda_build_config.yaml"
        )
    ):
        raise ValueError(
            "Cannot rerender with matrix in conda-forge.yml."
            " Please migrate matrix to conda_build_config.yaml and try again."
            " See https://github.com/conda-forge/conda-smithy/wiki/Release-Notes-3.0.0.rc1"
            " for more info."
        )

    if file_config.get("docker") and file_config.get("docker", {}).get(
        "image"
    ):
        raise ValueError(
            "Setting docker image in conda-forge.yml is removed now."
            " Use conda_build_config.yaml instead"
        )

    if (
        "build_with_mambabuild" in file_config
        and "conda_build_tool" not in file_config
    ):
        warnings.warn(
            "build_with_mambabuild is deprecated, use conda_build_tool instead",
            DeprecationWarning,
        )
        config["conda_build_tool"] = (
            "mambabuild" if config["build_with_mambabuild"] else "conda-build"
        )
    if file_config.get("conda_build_tool_deps"):
        raise ValueError(
            "Cannot set 'conda_build_tool_deps' directly. "
            "Use 'conda_build_tool' instead."
        )

    return config


def _legacy_compatibility_checks(config: dict, forge_dir):
    # An older conda-smithy used to have some files which should no longer exist,
    # remove those now.
    old_files = [
        "disabled_appveyor.yml",
        os.path.join("ci_support", "upload_or_check_non_existence.py"),
        "circle.yml",
        "appveyor.yml",
        os.path.join("ci_support", "checkout_merge_commit.sh"),
        os.path.join("ci_support", "fast_finish_ci_pr_build.sh"),
        os.path.join("ci_support", "run_docker_build.sh"),
        "LICENSE",
        "__pycache__",
        os.path.join(".github", "CONTRIBUTING.md"),
        os.path.join(".github", "ISSUE_TEMPLATE.md"),
        os.path.join(".github", "PULL_REQUEST_TEMPLATE.md"),
        os.path.join(".github", "workflows", "main.yml"),
    ]

    for old_file in old_files:
        if old_file.replace(os.sep, "/") in config["skip_render"]:
            continue
        remove_file_or_dir(os.path.join(forge_dir, old_file))

    # Older conda-smithy versions supported this with only one
    # entry. To avoid breakage, we are converting single elements
    # to a list of length one.
    for platform, providers in config["provider"].items():
        providers = conda_build.utils.ensure_list(providers)
        config["provider"][platform] = providers

    return config


def _load_forge_config(forge_dir, exclusive_config_file, forge_yml=None):
    config = _read_forge_config(forge_dir, forge_yml=forge_yml)

    for plat in ["linux", "osx", "win"]:
        if config["azure"]["timeout_minutes"] is not None:
            # fmt: off
            config["azure"][f"settings_{plat}"]["timeoutInMinutes"] \
                = config["azure"]["timeout_minutes"]
            # fmt: on
        if "name" in config["azure"][f"settings_{plat}"]["pool"]:
            del config["azure"][f"settings_{plat}"]["pool"]["vmImage"]

    if config["conda_forge_output_validation"]:
        config["secrets"] = sorted(
            set(
                config["secrets"]
                + ["FEEDSTOCK_TOKEN", "STAGING_BINSTAR_TOKEN"]
            )
        )

    target_platforms = sorted(config["build_platform"].keys())

    for platform_arch in target_platforms:
        config[platform_arch] = {"enabled": "True"}
        if platform_arch not in config["provider"]:
            config["provider"][platform_arch] = None

    config["noarch_platforms"] = conda_build.utils.ensure_list(
        config["noarch_platforms"]
    )

    # NOTE: Currently assuming these dependencies are name-only (no version constraints)
    if config["conda_build_tool"] == "mambabuild":
        config["conda_build_tool_deps"] = "conda-build boa"
    elif config["conda_build_tool"] == "conda-build+conda-libmamba-solver":
        config["conda_build_tool_deps"] = "conda-build conda-libmamba-solver"
    elif config["conda_build_tool"] == "rattler-build":
        config["conda_build_tool_deps"] = "rattler-build"
    else:
        config["conda_build_tool_deps"] = "conda-build"

    # NOTE: Currently assuming these dependencies are name-only (no version constraints)
    if config["conda_install_tool"] == "mamba":
        config["conda_install_tool_deps"] = "mamba"
    elif config["conda_install_tool"] in "conda":
        config["conda_install_tool_deps"] = "conda"
        if config.get("conda_solver") == "libmamba":
            config["conda_install_tool_deps"] += " conda-libmamba-solver"

    config["secrets"] = sorted(set(config["secrets"] + ["BINSTAR_TOKEN"]))

    if config["test_on_native_only"]:
        config["test"] = "native_and_emulated"

    if config["test"] is None:
        config["test"] = "all"

    # Set some more azure defaults
    config["azure"].setdefault("user_or_org", config["github"]["user_or_org"])

    log = yaml.safe_dump(config)
    logger.debug("## CONFIGURATION USED\n")
    logger.debug(log)
    logger.debug("## END CONFIGURATION\n")

    if config["provider"]["linux_aarch64"] == "default":
        config["provider"]["linux_aarch64"] = ["travis"]

    if config["provider"]["linux_aarch64"] == "native":
        config["provider"]["linux_aarch64"] = ["travis"]

    if config["provider"]["linux_ppc64le"] == "default":
        config["provider"]["linux_ppc64le"] = ["travis"]

    if config["provider"]["linux_ppc64le"] == "native":
        config["provider"]["linux_ppc64le"] = ["travis"]

    if config["provider"]["linux_s390x"] in {"default", "native"}:
        config["provider"]["linux_s390x"] = ["travis"]

    config["remote_ci_setup"] = _santize_remote_ci_setup(
        config["remote_ci_setup"]
    )
    if config["conda_install_tool"] == "conda":
        config["remote_ci_setup_update"] = [
            MatchSpec(pkg.strip('"').strip("'")).name
            for pkg in config["remote_ci_setup"]
        ]
    else:
        config["remote_ci_setup_update"] = config["remote_ci_setup"]

    if not config["github_actions"]["triggers"]:
        self_hosted = config["github_actions"]["self_hosted"]
        config["github_actions"]["triggers"] = (
            ["push"] if self_hosted else ["push", "pull_request"]
        )

    # Run the legacy checks for backwards compatibility
    config = _legacy_compatibility_checks(config, forge_dir)

    # Fallback handling set to azure, for platforms that are not fully specified by this time
    for platform, providers in config["provider"].items():
        for i, provider in enumerate(providers):
            if provider in {"default", "emulated"}:
                providers[i] = "azure"

    # Set the environment variable for the compiler stack
    os.environ["CF_COMPILER_STACK"] = config["compiler_stack"]
    # Set valid ranger for the supported platforms
    os.environ["CF_MIN_PY_VER"] = config["min_py_ver"]
    os.environ["CF_MAX_PY_VER"] = config["max_py_ver"]
    os.environ["CF_MIN_R_VER"] = config["min_r_ver"]
    os.environ["CF_MAX_R_VER"] = config["max_r_ver"]

    config["package"] = os.path.basename(forge_dir)
    if not config["github"]["repo_name"]:
        feedstock_name = os.path.basename(forge_dir)
        if not feedstock_name.endswith("-feedstock"):
            feedstock_name += "-feedstock"
        config["github"]["repo_name"] = feedstock_name
    config["exclusive_config_file"] = exclusive_config_file

    return config


def _get_metadata_from_feedstock_dir(
    feedstock_directory: Union[str, os.PathLike], forge_config: Dict[str, Any]
) -> Union[MetaData, RattlerBuildMetaData]:
    if forge_config and forge_config.get("conda_build_tool") == RATTLER_BUILD:
        meta = RattlerBuildMetaData(
            feedstock_directory,
        )
    else:
        meta = conda_build_render(
            feedstock_directory,
            permit_undefined_jinja=True,
            finalize=False,
            bypass_env_check=True,
            trim_skip=False,
        )[0][0]

    return meta


def get_feedstock_name_from_metadata(
    meta: Union[MetaData, RattlerBuildMetaData],
) -> str:
    """Get the feedstock name from a parsed meta.yaml or recipe.yaml."""
    return get_feedstock_name_from_meta(meta)


def get_feedstock_name_from_meta(meta):
    """Resolve the feedtstock name from the parsed meta.yaml."""
    if "feedstock-name" in meta.meta["extra"]:
        return meta.meta["extra"]["feedstock-name"]
    elif "parent_recipe" in meta.meta["extra"]:
        return meta.meta["extra"]["parent_recipe"]["name"]
    else:
        return meta.name()


def get_feedstock_about_from_meta(meta) -> dict:
    """Fetch the feedtstock about from the parsed meta.yaml."""
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


def get_yaml():
    # define global yaml API
    # roundrip-loader and allowing duplicate keys
    # for handling # [filter] / # [not filter]
    # Don't use a global variable for this as a global
    # variable will make conda-smithy thread unsafe.
    yaml = ruamel.yaml.YAML(typ="rt")
    yaml.allow_duplicate_keys = True
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
        )
    )
    mockos = MockOS()
    py_ver = "3.7"
    context = {"os": mockos, "environ": mockos.environ, "PY_VER": py_ver}
    content = env.from_string(text).render(context)
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
