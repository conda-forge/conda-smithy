import copy
import glob
import hashlib
import logging
import os
import pprint
import re
import subprocess
import sys
import textwrap
import time
import warnings
from collections import Counter, OrderedDict, namedtuple
from copy import deepcopy
from functools import lru_cache
from itertools import chain, product
from os import fspath
from pathlib import Path, PurePath

import requests
import yaml

# The `requests` lib uses `simplejson` instead of `json` when available.
# In consequence the same JSON library must be used or the `JSONDecodeError`
# used when catching an exception won't be the same as the one raised
# by `requests`.
try:
    import simplejson as json
except ImportError:
    import json

import conda_build.api
import conda_build.render
import conda_build.utils
import conda_build.variants
from conda.exceptions import InvalidVersionSpec
from conda.models.match_spec import MatchSpec
from conda.models.version import VersionOrder
from conda_build import __version__ as conda_build_version
from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment

from conda_smithy.feedstock_io import (
    copy_file,
    remove_file,
    remove_file_or_dir,
    set_exe_file,
    write_file,
)
from conda_smithy.utils import (
    get_feedstock_about_from_meta,
    get_feedstock_name_from_meta,
)
from conda_smithy.validate_schema import (
    CONDA_FORGE_YAML_DEFAULTS_FILE,
    validate_json_schema,
)

from . import __version__

conda_forge_content = os.path.abspath(os.path.dirname(__file__))

logger = logging.getLogger(__name__)

# feedstocks listed here are allowed to use GHA on
# conda-forge
# this should solve issues where other CI proviers have too many
# jobs and we need to change something via CI
SERVICE_FEEDSTOCKS = [
    "conda-forge-pinning-feedstock",
    "conda-forge-repodata-patches-feedstock",
    "conda-smithy-feedstock",
]
if "CONDA_SMITHY_SERVICE_FEEDSTOCKS" in os.environ:
    SERVICE_FEEDSTOCKS += os.environ["CONDA_SMITHY_SERVICE_FEEDSTOCKS"].split(
        ","
    )

# Cache lifetime in seconds, default 15min
CONDA_FORGE_PINNING_LIFETIME = int(
    os.environ.get("CONDA_FORGE_PINNING_LIFETIME", 15 * 60)
)


# use lru_cache to avoid repeating warnings endlessly;
# this keeps track of 10 different messages and then warns again
@lru_cache(10)
def warn_once(msg: str):
    logger.warning(msg)


def package_key(config, used_loop_vars, subdir):
    # get the build string from whatever conda-build makes of the configuration
    key = "".join(
        [
            k + str(config[k][0])
            for k in sorted(list(used_loop_vars))
            if k != "target_platform"
        ]
    )
    return key.replace("*", "_").replace(" ", "_")


def _ignore_match(ignore, rel):
    """Return true if rel or any of it's PurePath().parents are in ignore

    i.e. putting .github in skip_render will prevent rendering of anything
    named .github in the toplevel of the feedstock and anything below that as well
    """
    srch = {rel}
    srch.update(map(fspath, PurePath(rel).parents))
    logger.debug(f"srch:{srch}")
    logger.debug(f"ignore:{ignore}")
    if srch.intersection(ignore):
        logger.info(f"{rel} rendering is skipped")
        return True
    else:
        return False


def copytree(src, dst, ignore=(), root_dst=None):
    """This emulates shutil.copytree, but does so with our git file tracking, so that the new files
    are added to the repo"""
    if root_dst is None:
        root_dst = dst
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        rel = os.path.relpath(d, root_dst)
        if _ignore_match(ignore, rel):
            continue
        elif os.path.isdir(s):
            if not os.path.exists(d):
                os.makedirs(d)
            copytree(s, d, ignore, root_dst=root_dst)
        else:
            copy_file(s, d)


def merge_list_of_dicts(list_of_dicts):
    squished_dict = OrderedDict()
    for idict in list_of_dicts:
        for key, val in idict.items():
            if key not in squished_dict:
                squished_dict[key] = []
            squished_dict[key].extend(val)
    return squished_dict


def argsort(seq):
    return sorted(range(len(seq)), key=seq.__getitem__)


def sort_config(config, zip_key_groups):
    groups = copy.deepcopy(zip_key_groups)
    for i, group in enumerate(groups):
        groups[i] = [pkg for pkg in group if pkg in config.keys()]
    groups = [group for group in groups if group]

    sorting_order = {}
    for group in groups:
        if not group:
            continue
        list_of_values = []
        for idx in range(len(config[group[0]])):
            values = []
            for key in group:
                values.append(config[key][idx])
            list_of_values.append(tuple(values))

        order = argsort(list_of_values)
        for key in group:
            sorting_order[key] = order

    for key, value in config.items():
        if isinstance(value, (list, set, tuple)):
            val = list(value)
            if key in sorting_order:
                config[key] = [val[i] for i in sorting_order[key]]
            else:
                config[key] = sorted(val)
        if key == "pin_run_as_build":
            p = OrderedDict()
            for pkg in sorted(list(value.keys())):
                pkg_pins = value[pkg]
                d = OrderedDict()
                for pin in list(reversed(sorted(pkg_pins.keys()))):
                    d[pin] = pkg_pins[pin]
                p[pkg] = d
            config[key] = p


def break_up_top_level_values(top_level_keys, squished_variants):
    """top-level values make up CI configurations.  We need to break them up
    into individual files."""

    accounted_for_keys = set()

    # handle grouping from zip_keys for everything in conform_dict
    zip_key_groups = []
    if "zip_keys" in squished_variants:
        zip_key_groups = squished_variants["zip_keys"]
        if zip_key_groups and not isinstance(zip_key_groups[0], list):
            zip_key_groups = [zip_key_groups]
    zipped_configs = []
    top_level_dimensions = []
    for key in top_level_keys:
        if key in accounted_for_keys:
            # remove the used variables from the collection of all variables - we have them in the
            #    other collections now
            continue
        if any(key in group for group in zip_key_groups):
            for group in zip_key_groups:
                if key in group:
                    accounted_for_keys.update(set(group))
                    # create a list of dicts that represent the different permutations that are
                    #    zipped together.  Each dict in this list will be a different top-level
                    #    config in its own file

                    zipped_config = []
                    top_level_config_dict = OrderedDict()
                    for idx, variant_key in enumerate(squished_variants[key]):
                        top_level_config = []
                        for k in group:
                            if k in top_level_keys:
                                top_level_config.append(
                                    squished_variants[k][idx]
                                )
                        top_level_config = tuple(top_level_config)
                        if top_level_config not in top_level_config_dict:
                            top_level_config_dict[top_level_config] = []
                        top_level_config_dict[top_level_config].append(
                            {k: [squished_variants[k][idx]] for k in group}
                        )
                    # merge dicts with the same `key` if `key` is repeated in the group.
                    for _, variant_key_val in top_level_config_dict.items():
                        squished_dict = merge_list_of_dicts(variant_key_val)
                        zipped_config.append(squished_dict)
                    zipped_configs.append(zipped_config)
                    for k in group:
                        del squished_variants[k]
                    break

        else:
            # dimension slice is just this one variable, all other dimensions keep their variability
            top_level_dimensions.append(
                [{key: [val]} for val in squished_variants[key]]
            )
            del squished_variants[key]

    configs = []
    dimensions = []

    # sort values so that the diff doesn't show randomly changing order

    if "zip_keys" in squished_variants:
        zip_key_groups = squished_variants["zip_keys"]

    sort_config(squished_variants, zip_key_groups)

    for zipped_config in zipped_configs:
        for config in zipped_config:
            sort_config(config, zip_key_groups)

    if top_level_dimensions:
        dimensions.extend(top_level_dimensions)
    if zipped_configs:
        dimensions.extend(zipped_configs)
    if squished_variants:
        dimensions.append([squished_variants])
    for permutation in product(*dimensions):
        config = dict()
        for perm in permutation:
            config.update(perm)
        configs.append(config)

    return configs


def _package_var_name(pkg):
    return pkg.replace("-", "_")


def _trim_unused_zip_keys(all_used_vars):
    """Remove unused keys in zip_keys sets, so that they don't cause unnecessary missing value
    errors"""
    groups = all_used_vars.get("zip_keys", [])
    if groups and not any(isinstance(groups[0], obj) for obj in (list, tuple)):
        groups = [groups]
    used_groups = []
    for group in groups:
        used_keys_in_group = [k for k in group if k in all_used_vars]
        if len(used_keys_in_group) > 1:
            used_groups.append(used_keys_in_group)
    if used_groups:
        all_used_vars["zip_keys"] = used_groups
    elif "zip_keys" in all_used_vars:
        del all_used_vars["zip_keys"]


def _trim_unused_pin_run_as_build(all_used_vars):
    """Remove unused keys in pin_run_as_build sets"""
    pkgs = all_used_vars.get("pin_run_as_build", {})
    used_pkgs = {}
    if pkgs:
        for key in pkgs.keys():
            if _package_var_name(key) in all_used_vars:
                used_pkgs[key] = pkgs[key]
    if used_pkgs:
        all_used_vars["pin_run_as_build"] = used_pkgs
    elif "pin_run_as_build" in all_used_vars:
        del all_used_vars["pin_run_as_build"]


def _get_used_key_values_by_input_order(
    squished_input_variants,
    squished_used_variants,
    all_used_vars,
):
    used_key_values = {
        key: squished_input_variants[key]
        for key in all_used_vars
        if key in squished_input_variants
    }
    logger.debug(f"initial used_key_values {pprint.pformat(used_key_values)}")

    # we want remove any used key values not in used variants and make sure they follow the
    #   input order
    # zipped keys are a special case since they are ordered by the list of tuple of zipped
    #   key values
    # so we do the zipped keys first and then do the rest
    zipped_tuples = {}
    zipped_keys = set()
    for keyset in squished_input_variants["zip_keys"]:
        zipped_tuples[tuple(keyset)] = list(
            zip(*[squished_input_variants[k] for k in keyset])
        )
        zipped_keys |= set(keyset)
    logger.debug(f"zipped_keys {pprint.pformat(zipped_keys)}")
    logger.debug(f"zipped_tuples {pprint.pformat(zipped_tuples)}")

    for keyset, tuples in zipped_tuples.items():
        # for each set of zipped keys from squished_input_variants,
        # we trim them down to what is in squished_used_variants
        used_keyset = []
        used_keyset_inds = []
        for k in keyset:
            if k in squished_used_variants:
                used_keyset.append(k)
                used_keyset_inds.append(keyset.index(k))
        used_keyset = tuple(used_keyset)
        used_keyset_inds = tuple(used_keyset_inds)

        # if we find nothing, keep going
        if not used_keyset:
            continue

        # this trims the zipped tuples down to the used keys
        used_tuples = tuple(
            [
                tuple(
                    [
                        tup[used_keyset_ind]
                        for used_keyset_ind in used_keyset_inds
                    ]
                )
                for tup in tuples
            ]
        )
        logger.debug(f"used_keyset {pprint.pformat(used_keyset)}")
        logger.debug(f"used_keyset_inds {pprint.pformat(used_keyset_inds)}")
        logger.debug(f"used_tuples {pprint.pformat(used_tuples)}")

        # this is the set of tuples that we want to keep, but need to be reordered
        used_tuples_to_be_reordered = set(
            list(zip(*[squished_used_variants[k] for k in used_keyset]))
        )
        logger.debug(
            f"used_tuples_to_be_reordered {pprint.pformat(used_tuples_to_be_reordered)}"
        )

        # we double check the logic above by looking to ensure everything in
        #   the squished_used_variants
        # is in the squished_input_variants
        used_tuples_set = set(used_tuples)
        logger.debug(
            "are all used tuples in input tuples? %s",
            all(
                used_tuple in used_tuples_set
                for used_tuple in used_tuples_to_be_reordered
            ),
        )

        # now we do the final rdering
        final_used_tuples = tuple(
            [tup for tup in used_tuples if tup in used_tuples_to_be_reordered]
        )
        logger.debug(f"final_used_tuples {pprint.pformat(final_used_tuples)}")

        # now we reconstruct the list of values per key and replace in used_key_values
        # we keep only keys in all_used_vars
        for i, k in enumerate(used_keyset):
            if k in all_used_vars:
                used_key_values[k] = [tup[i] for tup in final_used_tuples]

    # finally, we handle the rest of the keys that are not zipped
    for k, v in squished_used_variants.items():
        if k in all_used_vars and k not in zipped_keys:
            used_key_values[k] = v

    logger.debug(
        f"post input reorder used_key_values {pprint.pformat(used_key_values)}"
    )

    return used_key_values, zipped_keys


def _merge_deployment_target(container_of_dicts, has_macdt):
    """
    For a collection of variant dictionaries, merge deployment target specs.

    - The "old" way is MACOSX_DEPLOYMENT_TARGET, the new way is c_stdlib_version;
      For now, take the maximum to populate both.
    - In any case, populate MACOSX_DEPLOYMENT_TARGET, as that is the key picked
      up by https://github.com/conda-forge/conda-forge-ci-setup-feedstock
    - If MACOSX_SDK_VERSION is lower than the merged value from the previous step,
      update it to match the merged value.
    """
    result = []
    for var_dict in container_of_dicts:
        # cases where no updates are necessary
        if not var_dict.get("target_platform", "dummy").startswith("osx"):
            result.append(var_dict)
            continue
        if "c_stdlib_version" not in var_dict:
            result.append(var_dict)
            continue
        # case where we need to do processing
        v_stdlib = var_dict["c_stdlib_version"]
        macdt = var_dict.get("MACOSX_DEPLOYMENT_TARGET", v_stdlib)
        sdk = var_dict.get("MACOSX_SDK_VERSION", v_stdlib)
        # error out if someone puts in a range of versions; we need a single version
        try:
            stdlib_lt_macdt = VersionOrder(v_stdlib) < VersionOrder(macdt)
            sdk_lt_stdlib = VersionOrder(sdk) < VersionOrder(v_stdlib)
            sdk_lt_macdt = VersionOrder(sdk) < VersionOrder(macdt)
        except InvalidVersionSpec:
            raise ValueError(
                "all of c_stdlib_version/MACOSX_DEPLOYMENT_TARGET/"
                "MACOSX_SDK_VERSION need to be a single version, "
                "not a version range!"
            )
        if v_stdlib != macdt:
            # determine maximum version and use it to populate both
            v_stdlib = macdt if stdlib_lt_macdt else v_stdlib
            msg = (
                "Conflicting specification for minimum macOS deployment target!\n"
                "If your conda_build_config.yaml sets `MACOSX_DEPLOYMENT_TARGET`, "
                "please change the name of that key to `c_stdlib_version`!\n"
                f"Using {v_stdlib}=max(c_stdlib_version, MACOSX_DEPLOYMENT_TARGET)."
            )
            # we don't want to warn for recipes that do not use MACOSX_DEPLOYMENT_TARGET
            # in the local CBC, but only inherit it from the global pinning
            if has_macdt:
                warn_once(msg)

        if sdk_lt_stdlib or sdk_lt_macdt:
            sdk_lt_merged = VersionOrder(sdk) < VersionOrder(v_stdlib)
            sdk = v_stdlib if sdk_lt_merged else sdk
            msg = (
                "Conflicting specification for minimum macOS SDK version!\n"
                "If your conda_build_config.yaml sets `MACOSX_SDK_VERSION`, "
                "it must be larger or equal than `c_stdlib_version` "
                "(which is also influenced by the global pinning)!\n"
                f"Using {sdk}=max(c_stdlib_version, MACOSX_SDK_VERSION)."
            )
            warn_once(msg)

        # we set MACOSX_DEPLOYMENT_TARGET to match c_stdlib_version,
        # for ease of use in conda-forge-ci-setup;
        # use new dictionary to avoid mutating existing var_dict in place
        new_dict = conda_build.utils.HashableDict(
            {
                **var_dict,
                "c_stdlib_version": v_stdlib,
                "MACOSX_DEPLOYMENT_TARGET": v_stdlib,
                "MACOSX_SDK_VERSION": sdk,
            }
        )
        result.append(new_dict)
    # ensure we keep type of wrapper container (set stays set, etc.)
    return type(container_of_dicts)(result)


def _collapse_subpackage_variants(
    list_of_metas, root_path, platform, arch, forge_config
):
    """Collapse all subpackage node variants into one aggregate collection of used variables

    We get one node per output, but a given recipe can have multiple outputs.  Each output
    can have its own used_vars, and we must unify all of the used variables for all of the
    outputs"""

    # things we consider "top-level" are things that we loop over with CI jobs.  We don't loop over
    #     outputs with CI jobs.
    top_level_loop_vars = set()

    all_used_vars = set()
    all_variants = set()

    is_noarch = True

    for meta in list_of_metas:
        all_used_vars.update(meta.get_used_vars())
        # this is a hack to work around the fact that we specify mpi variants
        # via an `mpi` variable in the CBC but we do not parse our recipes
        # twice to ensure the pins given by the variant also show up in the
        # smithy CI support scripts
        # future MPI variants have to be added here
        if "mpi" in all_used_vars:
            all_used_vars.update(
                ["mpich", "openmpi", "msmpi", "mpi_serial", "impi"]
            )
        all_variants.update(
            conda_build.utils.HashableDict(v) for v in meta.config.variants
        )

        all_variants.add(conda_build.utils.HashableDict(meta.config.variant))

        if not meta.noarch:
            is_noarch = False

    # determine if MACOSX_DEPLOYMENT_TARGET appears in recipe-local CBC;
    # all metas in list_of_metas come from same recipe, so path is identical
    cbc_path = os.path.join(list_of_metas[0].path, "conda_build_config.yaml")
    has_macdt = False
    if os.path.exists(cbc_path):
        with open(cbc_path) as f:
            lines = f.readlines()
        if any(re.match(r"^\s*MACOSX_DEPLOYMENT_TARGET:", x) for x in lines):
            has_macdt = True

    # on osx, merge MACOSX_DEPLOYMENT_TARGET & c_stdlib_version to max of either; see #1884
    all_variants = _merge_deployment_target(all_variants, has_macdt)

    top_level_loop_vars = list_of_metas[0].get_used_loop_vars(
        force_top_level=True
    )
    top_level_vars = list_of_metas[0].get_used_vars(force_top_level=True)
    if "target_platform" in all_used_vars:
        top_level_loop_vars.add("target_platform")

    logger.debug(f"initial all_used_vars {pprint.pformat(all_used_vars)}")

    # this is the initial collection of all variants before we discard any.  "Squishing"
    #     them is necessary because the input form is already broken out into one matrix
    #     configuration per item, and we want a single dict, with each key representing many values
    squished_input_variants = conda_build.variants.list_of_dicts_to_dict_of_lists(
        # ensure we update the input_variants in the same way as all_variants
        _merge_deployment_target(
            list_of_metas[0].config.input_variants, has_macdt
        )
    )
    squished_used_variants = (
        conda_build.variants.list_of_dicts_to_dict_of_lists(list(all_variants))
    )
    logger.debug(
        f"squished_input_variants {pprint.pformat(squished_input_variants)}"
    )
    logger.debug(
        f"squished_used_variants {pprint.pformat(squished_used_variants)}"
    )

    # these are variables that only occur in the top level, and thus won't show up as loops in the
    #     above collection of all variants.  We need to transfer them from the input_variants.
    preserve_top_level_loops = set(top_level_loop_vars) - set(all_used_vars)
    logger.debug(f"preserve_top_level_loops {preserve_top_level_loops}")

    # Add in some variables that should always be preserved
    always_keep_keys = {
        "zip_keys",
        "pin_run_as_build",
        "MACOSX_DEPLOYMENT_TARGET",
        "MACOSX_SDK_VERSION",
        "macos_min_version",
        "macos_machine",
        "channel_sources",
        "channel_targets",
        "docker_image",
        "build_number_decrement",
        # The following keys are required for some of our aarch64 builds
        # Added in https://github.com/conda-forge/conda-forge-pinning-feedstock/pull/180
        "cdt_arch",
        "cdt_name",
        "BUILD",
    }

    if not is_noarch:
        always_keep_keys.add("target_platform")

    if forge_config["github_actions"]["self_hosted"]:
        always_keep_keys.add("github_actions_labels")

    all_used_vars.update(always_keep_keys)
    all_used_vars.update(top_level_vars)

    logger.debug(f"final all_used_vars {pprint.pformat(all_used_vars)}")
    logger.debug(f"top_level_vars {pprint.pformat(top_level_vars)}")
    logger.debug(f"top_level_loop_vars {pprint.pformat(top_level_loop_vars)}")

    used_key_values, used_zipped_vars = _get_used_key_values_by_input_order(
        squished_input_variants,
        squished_used_variants,
        all_used_vars,
    )

    for k in preserve_top_level_loops:
        # we do not stomp on keys in zips since their order matters
        if k not in used_zipped_vars:
            used_key_values[k] = squished_input_variants[k]

    _trim_unused_zip_keys(used_key_values)
    _trim_unused_pin_run_as_build(used_key_values)

    # to deduplicate potentially zipped keys, we blow out the collection of variables, then
    #     do a set operation, then collapse it again

    used_key_values = conda_build.variants.dict_of_lists_to_list_of_dicts(
        used_key_values
    )
    used_key_values = {
        conda_build.utils.HashableDict(variant) for variant in used_key_values
    }
    used_key_values = conda_build.variants.list_of_dicts_to_dict_of_lists(
        list(used_key_values)
    )

    _trim_unused_zip_keys(used_key_values)
    _trim_unused_pin_run_as_build(used_key_values)

    logger.debug(f"final used_key_values {pprint.pformat(used_key_values)}")

    return (
        break_up_top_level_values(top_level_loop_vars, used_key_values),
        top_level_loop_vars,
    )


def _yaml_represent_ordereddict(yaml_representer, data):
    # represent_dict processes dict-likes with a .sort() method or plain iterables of key-value
    #     pairs. Only for the latter it never sorts and retains the order of the OrderedDict.
    return yaml.representer.SafeRepresenter.represent_dict(
        yaml_representer, data.items()
    )


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


def finalize_config(config, platform, arch, forge_config):
    """For configs without essential parameters like docker_image
    add fallback value.
    """
    build_platform = forge_config["build_platform"][f"{platform}_{arch}"]
    if build_platform.startswith("linux"):
        if "docker_image" in config:
            config["docker_image"] = [config["docker_image"][0]]
        else:
            config["docker_image"] = [forge_config["docker"]["fallback_image"]]

        if "zip_keys" in config:
            for ziplist in config["zip_keys"]:
                if "docker_image" in ziplist:
                    for key in ziplist:
                        if key != "docker_image":
                            config[key] = [config[key][0]]

    return config


def dump_subspace_config_files(
    metas, root_path, platform, arch, upload, forge_config
):
    """With conda-build 3, it handles the build matrix.  We take what it spits out, and write a
    config.yaml file for each matrix entry that it spits out.  References to a specific file
    replace all of the old environment variables that specified a matrix entry.
    """

    # identify how to break up the complete set of used variables.  Anything considered
    #     "top-level" should be broken up into a separate CI job.

    configs, top_level_loop_vars = _collapse_subpackage_variants(
        metas,
        root_path,
        platform,
        arch,
        forge_config,
    )
    logger.debug(f"collapsed subspace config files: {pprint.pformat(configs)}")

    # get rid of the special object notation in the yaml file for objects that we dump
    yaml.add_representer(set, yaml.representer.SafeRepresenter.represent_list)
    yaml.add_representer(
        tuple, yaml.representer.SafeRepresenter.represent_list
    )
    yaml.add_representer(OrderedDict, _yaml_represent_ordereddict)

    platform_arch = f"{platform}-{arch}"

    result = []
    for config in configs:
        config_name = "{}_{}".format(
            f"{platform}_{arch}",
            package_key(config, top_level_loop_vars, metas[0].config.subdir),
        )
        short_config_name = config_name
        if len(short_config_name) >= 49:
            h = hashlib.sha256(config_name.encode("utf-8")).hexdigest()[:10]
            short_config_name = config_name[:35] + "_h" + h
        if len("conda-forge-build-done-" + config_name) >= 250:
            # Shorten file name length to avoid hitting maximum filename limits.
            config_name = short_config_name

        out_folder = os.path.join(root_path, ".ci_support")
        out_path = os.path.join(out_folder, config_name) + ".yaml"
        if not os.path.isdir(out_folder):
            os.makedirs(out_folder)

        config = finalize_config(config, platform, arch, forge_config)
        logger.debug(f"finalized config file: {pprint.pformat(config)}")

        with write_file(out_path) as f:
            yaml.dump(config, f, default_flow_style=False)

        target_platform = config.get("target_platform", [platform_arch])[0]
        result.append(
            {
                "config_name": config_name,
                "platform": target_platform,
                "upload": upload,
                "config": config,
                "short_config_name": short_config_name,
                "build_platform": forge_config["build_platform"][
                    f"{platform}_{arch}"
                ].replace("_", "-"),
            }
        )
    return sorted(result, key=lambda x: x["config_name"])


def _get_fast_finish_script(
    provider_name, forge_config, forge_dir, fast_finish_text
):
    get_fast_finish_script = ""
    fast_finish_script = ""
    tooling_branch = forge_config["github"]["tooling_branch_name"]

    cfbs_fpath = os.path.join(
        forge_dir, forge_config["recipe_dir"], "ff_ci_pr_build.py"
    )
    if provider_name == "appveyor":
        if os.path.exists(cfbs_fpath):
            fast_finish_script = "{recipe_dir}\\ff_ci_pr_build".format(
                recipe_dir=forge_config["recipe_dir"]
            )
        else:
            get_fast_finish_script = '''powershell -Command "(New-Object Net.WebClient).DownloadFile('https://raw.githubusercontent.com/conda-forge/conda-forge-ci-setup-feedstock/{branch}/recipe/conda_forge_ci_setup/ff_ci_pr_build.py', 'ff_ci_pr_build.py')"'''  # NOQA
            fast_finish_script += "ff_ci_pr_build"
            fast_finish_text += "del {fast_finish_script}.py"

        fast_finish_text = fast_finish_text.format(
            get_fast_finish_script=get_fast_finish_script.format(
                branch=tooling_branch
            ),
            fast_finish_script=fast_finish_script,
        )

        fast_finish_text = fast_finish_text.strip()
        fast_finish_text = fast_finish_text.replace("\n", "\n        ")
    else:
        # If the recipe supplies its own ff_ci_pr_build.py script,
        # we use it instead of the global one.
        if os.path.exists(cfbs_fpath):
            get_fast_finish_script += (
                "cat {recipe_dir}/ff_ci_pr_build.py".format(
                    recipe_dir=forge_config["recipe_dir"]
                )
            )
        else:
            get_fast_finish_script += "curl https://raw.githubusercontent.com/conda-forge/conda-forge-ci-setup-feedstock/{branch}/recipe/conda_forge_ci_setup/ff_ci_pr_build.py"  # NOQA

        fast_finish_text = fast_finish_text.format(
            get_fast_finish_script=get_fast_finish_script.format(
                branch=tooling_branch
            )
        )

        fast_finish_text = fast_finish_text.strip()
    return fast_finish_text


def migrate_combined_spec(combined_spec, forge_dir, config, forge_config):
    """CFEP-9 variant migrations

    Apply the list of migrations configurations to the build (in the correct sequence)
    This will be used to change the variant within the list of MetaData instances,
    and return the migrated variants.

    This has to happend before the final variant files are computed.

    The method for application is determined by the variant algebra as defined by CFEP-9

    """
    combined_spec = combined_spec.copy()
    if "migration_fns" not in forge_config:
        migrations = set_migration_fns(forge_dir, forge_config)
    migrations = forge_config["migration_fns"]

    from .variant_algebra import parse_variant, variant_add

    migration_variants = [
        (fn, parse_variant(open(fn).read(), config=config))
        for fn in migrations
    ]

    migration_variants.sort(key=lambda fn_v: (fn_v[1]["migrator_ts"], fn_v[0]))
    if len(migration_variants):
        logger.info(
            f"Applying migrations: {','.join(k for k, v in migration_variants)}"
        )

    for migrator_file, migration in migration_variants:
        if "migrator_ts" in migration:
            del migration["migrator_ts"]
        if len(migration):
            combined_spec = variant_add(combined_spec, migration)
    return combined_spec


def _conda_build_api_render_for_smithy(
    recipe_path,
    config=None,
    variants=None,
    permit_unsatisfiable_variants=True,
    finalize=True,
    bypass_env_check=False,
    **kwargs,
):
    """This function works just like conda_build.api.render, but it returns all of metadata objects
    regardless of whether they produce a unique package hash / name.

    When conda-build renders a recipe, it returns the metadata for each unique file generated. If a key
    we use at the top-level in a multi-output recipe does not explicitly impact one of the recipe outputs
    (i.e., an output's recipe doesn't use that key), then conda-build will not return all of the variants
    for that key.

    This behavior is not what we do in conda-forge (i.e., we want all variants that are not explicitly
    skipped even if some of the keys in the variants are not explicitly used in an output).

    The most robust way to handle this is to write a custom function that returns metadata for each of
    the variants in the full exploded matrix that involve a key used by the recipe anywhere,
    except the ones that the recipe skips.
    """

    from conda.exceptions import NoPackagesFoundError
    from conda_build.config import get_or_merge_config
    from conda_build.exceptions import DependencyNeedsBuildingError
    from conda_build.render import finalize_metadata, render_recipe

    config = get_or_merge_config(config, **kwargs)

    metadata_tuples = render_recipe(
        recipe_path,
        bypass_env_check=bypass_env_check,
        no_download_source=config.no_download_source,
        config=config,
        variants=variants,
        permit_unsatisfiable_variants=permit_unsatisfiable_variants,
    )
    output_metas = []
    for meta, download, render_in_env in metadata_tuples:
        if not meta.skip() or not config.trim_skip:
            for od, om in meta.get_output_metadata_set(
                permit_unsatisfiable_variants=permit_unsatisfiable_variants,
                permit_undefined_jinja=not finalize,
                bypass_env_check=bypass_env_check,
            ):
                if not om.skip() or not config.trim_skip:
                    if "type" not in od or od["type"] == "conda":
                        if finalize and not om.final:
                            try:
                                om = finalize_metadata(
                                    om,
                                    permit_unsatisfiable_variants=permit_unsatisfiable_variants,
                                )
                            except (
                                DependencyNeedsBuildingError,
                                NoPackagesFoundError,
                            ):
                                if not permit_unsatisfiable_variants:
                                    raise

                        # remove outputs section from output objects for simplicity
                        if not om.path and (
                            outputs := om.get_section("outputs")
                        ):
                            om.parent_outputs = outputs
                            del om.meta["outputs"]

                        output_metas.append((om, download, render_in_env))
                    else:
                        output_metas.append((om, download, render_in_env))

    return output_metas


def _render_ci_provider(
    provider_name,
    jinja_env,
    forge_config,
    forge_dir,
    platforms,
    archs,
    fast_finish_text,
    platform_target_path,
    platform_template_file,
    platform_specific_setup,
    keep_noarchs=None,
    extra_platform_files={},
    upload_packages=[],
    return_metadata=False,
):
    if keep_noarchs is None:
        keep_noarchs = [False] * len(platforms)

    metas_list_of_lists = []
    enable_platform = [False] * len(platforms)
    for i, (platform, arch, keep_noarch) in enumerate(
        zip(platforms, archs, keep_noarchs)
    ):
        os.environ["CONFIG_VERSION"] = forge_config["config_version"]
        os.environ["BUILD_PLATFORM"] = forge_config["build_platform"][
            f"{platform}_{arch}"
        ].replace("_", "-")

        # set the environment variable for OS version
        if platform == "linux":
            ver = forge_config["os_version"][f"{platform}_{arch}"]
            if ver:
                os.environ["DEFAULT_LINUX_VERSION"] = ver

        # detect if `compiler('cuda')` is used in meta.yaml,
        # and set appropriate environment variable
        with open(
            os.path.join(forge_dir, forge_config["recipe_dir"], "meta.yaml")
        ) as f:
            meta_lines = f.readlines()
        # looking for `compiler('cuda')` with both quote variants;
        # do not match if there is a `#` somewhere before on the line
        pat = re.compile(r"^[^\#]*compiler\((\"cuda\"|\'cuda\')\).*")
        for ml in meta_lines:
            if pat.match(ml):
                os.environ["CF_CUDA_ENABLED"] = "True"

        config = conda_build.config.get_or_merge_config(
            None,
            exclusive_config_file=forge_config["exclusive_config_file"],
            platform=platform,
            arch=arch,
        )

        # Get the combined variants from normal variant locations prior to running migrations
        (
            combined_variant_spec,
            _,
        ) = conda_build.variants.get_package_combined_spec(
            os.path.join(forge_dir, forge_config["recipe_dir"]), config=config
        )

        migrated_combined_variant_spec = migrate_combined_spec(
            combined_variant_spec,
            forge_dir,
            config,
            forge_config,
        )
        for channel_target in migrated_combined_variant_spec.get(
            "channel_targets", []
        ):
            if (
                channel_target.startswith("conda-forge ")
                and provider_name == "github_actions"
                and not forge_config["github_actions"]["self_hosted"]
            ):
                raise RuntimeError(
                    "Using github_actions as the CI provider inside "
                    "conda-forge github org is not allowed in order "
                    "to avoid a denial of service for other infrastructure."
                )

            # we skip travis builds for anything but aarch64, ppc64le and s390x
            # due to their current open-source policies around usage
            if (
                channel_target.startswith("conda-forge ")
                and provider_name == "travis"
                and (
                    platform != "linux"
                    or arch not in ["aarch64", "ppc64le", "s390x"]
                )
            ):
                raise RuntimeError(
                    "Travis CI can only be used for 'linux_aarch64', "
                    "'linux_ppc64le' or 'linux_s390x' native builds"
                    f", not '{platform}_{arch}', to avoid using open-source build minutes!"
                )

        # AFAIK there is no way to get conda build to ignore the CBC yaml
        # in the recipe. This one can mess up migrators applied with local
        # CBC yaml files where variants in the migrators are not in the CBC.
        # Thus we move it out of the way.
        # TODO: upstream this as a flag in conda-build
        try:
            _recipe_cbc = os.path.join(
                forge_dir,
                forge_config["recipe_dir"],
                "conda_build_config.yaml",
            )
            if os.path.exists(_recipe_cbc):
                os.rename(_recipe_cbc, _recipe_cbc + ".conda.smithy.bak")

            channel_sources = migrated_combined_variant_spec.get(
                "channel_sources", [""]
            )[0].split(",")
            metas = _conda_build_api_render_for_smithy(
                os.path.join(forge_dir, forge_config["recipe_dir"]),
                platform=platform,
                arch=arch,
                ignore_system_variants=True,
                variants=migrated_combined_variant_spec,
                permit_undefined_jinja=True,
                finalize=False,
                bypass_env_check=True,
                channel_urls=channel_sources,
            )
        finally:
            if os.path.exists(_recipe_cbc + ".conda.smithy.bak"):
                os.rename(_recipe_cbc + ".conda.smithy.bak", _recipe_cbc)

        # render returns some download & reparsing info that we don't care about
        metas = [m for m, _, _ in metas]

        if not keep_noarch:
            to_delete = []
            for idx, meta in enumerate(metas):
                if meta.noarch:
                    # do not build noarch, including noarch: python, packages on Travis CI.
                    to_delete.append(idx)
            for idx in reversed(to_delete):
                del metas[idx]

        for meta in metas:
            if not meta.skip():
                enable_platform[i] = True
        metas_list_of_lists.append(metas)

    if not any(enable_platform):
        # There are no cases to build (not even a case without any special
        # dependencies), so remove the run_docker_build.sh if it exists.
        forge_config[provider_name]["enabled"] = False

        target_fnames = [platform_target_path]
        if extra_platform_files:
            for val in extra_platform_files.values():
                target_fnames.extend(val)
        for each_target_fname in target_fnames:
            remove_file(each_target_fname)
    else:
        forge_config[provider_name]["enabled"] = True
        fancy_name = {
            "linux_64": "Linux",
            "osx_64": "OSX",
            "win_64": "Windows",
            "linux_aarch64": "Arm64",
            "linux_ppc64le": "PowerPC64",
        }
        fancy_platforms = []
        unfancy_platforms = set()

        configs = []
        for metas, platform, arch, enable, upload in zip(
            metas_list_of_lists,
            platforms,
            archs,
            enable_platform,
            upload_packages,
        ):
            if enable:
                configs.extend(
                    dump_subspace_config_files(
                        metas, forge_dir, platform, arch, upload, forge_config
                    )
                )

                plat_arch = f"{platform}_{arch}"
                forge_config[plat_arch]["enabled"] = True
                fancy_platforms.append(fancy_name.get(plat_arch, plat_arch))
                unfancy_platforms.add(plat_arch)
            elif platform in extra_platform_files:
                for each_target_fname in extra_platform_files[platform]:
                    remove_file(each_target_fname)

        for key in extra_platform_files.keys():
            if key != "common" and key not in platforms:
                for each_target_fname in extra_platform_files[key]:
                    remove_file(each_target_fname)

        forge_config[provider_name]["platforms"] = ",".join(fancy_platforms)
        forge_config[provider_name]["all_platforms"] = list(unfancy_platforms)

        # Copy the config now. Changes below shouldn't persist across CI.
        forge_config = deepcopy(forge_config)

        forge_config["configs"] = configs

        forge_config["fast_finish"] = _get_fast_finish_script(
            provider_name,
            forge_dir=forge_dir,
            forge_config=forge_config,
            fast_finish_text=fast_finish_text,
        )

        # If the recipe has its own conda_forge_ci_setup package, then
        # install that
        if os.path.exists(
            os.path.join(
                forge_dir,
                forge_config["recipe_dir"],
                "conda_forge_ci_setup",
                "__init__.py",
            )
        ) and os.path.exists(
            os.path.join(
                forge_dir,
                forge_config["recipe_dir"],
                "setup.py",
            )
        ):
            forge_config["local_ci_setup"] = True
        else:
            forge_config["local_ci_setup"] = False

        # hook for extending with whatever platform specific junk we need.
        #     Function passed in as argument
        build_platforms = OrderedDict()
        for platform, arch, enable in zip(platforms, archs, enable_platform):
            if enable:
                build_platform = forge_config["build_platform"][
                    f"{platform}_{arch}"
                ].split("_")[0]
                build_platforms[build_platform] = True

        for platform in build_platforms.keys():
            platform_specific_setup(
                jinja_env=jinja_env,
                forge_dir=forge_dir,
                forge_config=forge_config,
                platform=platform,
            )

        template = jinja_env.get_template(platform_template_file)
        with write_file(platform_target_path) as fh:
            fh.write(template.render(**forge_config))

    # circleci needs a placeholder file of sorts - always write the output, even if no metas
    if provider_name == "circle":
        template = jinja_env.get_template(platform_template_file)
        with write_file(platform_target_path) as fh:
            fh.write(template.render(**forge_config))
    # TODO: azure-pipelines might need the same as circle
    if return_metadata:
        return dict(
            forge_config=forge_config,
            metas_list_of_lists=metas_list_of_lists,
            platforms=platforms,
            archs=archs,
            enable_platform=enable_platform,
            provider_name=provider_name,
        )
    else:
        return forge_config


def _get_build_setup_line(forge_dir, platform, forge_config):
    # If the recipe supplies its own run_conda_forge_build_setup script_linux,
    # we use it instead of the global one.
    if platform == "linux":
        cfbs_fpath = os.path.join(
            forge_dir,
            forge_config["recipe_dir"],
            "run_conda_forge_build_setup_linux",
        )
    elif platform == "win":
        cfbs_fpath = os.path.join(
            forge_dir,
            forge_config["recipe_dir"],
            "run_conda_forge_build_setup_win.bat",
        )
    else:
        cfbs_fpath = os.path.join(
            forge_dir,
            forge_config["recipe_dir"],
            "run_conda_forge_build_setup_osx",
        )

    build_setup = ""
    if os.path.exists(cfbs_fpath):
        if platform == "linux":
            build_setup += textwrap.dedent(
                """\
                # Overriding global run_conda_forge_build_setup_linux with local copy.
                source ${RECIPE_ROOT}/run_conda_forge_build_setup_linux

            """
            )
        elif platform == "win":
            build_setup += textwrap.dedent(
                """\
                :: Overriding global run_conda_forge_build_setup_win with local copy.
                CALL {recipe_dir}\\run_conda_forge_build_setup_win
            """.format(
                    recipe_dir=forge_config["recipe_dir"]
                )
            )
        else:
            build_setup += textwrap.dedent(
                """\
                # Overriding global run_conda_forge_build_setup_osx with local copy.
                source {recipe_dir}/run_conda_forge_build_setup_osx
            """.format(
                    recipe_dir=forge_config["recipe_dir"]
                )
            )
    else:
        if platform == "win":
            build_setup += textwrap.dedent(
                """\
                CALL run_conda_forge_build_setup

            """
            )
        else:
            build_setup += textwrap.dedent(
                """\
            source run_conda_forge_build_setup

            """
            )
    return build_setup


def _circle_specific_setup(jinja_env, forge_config, forge_dir, platform):
    if platform == "linux":
        yum_build_setup = generate_yum_requirements(forge_config, forge_dir)
        if yum_build_setup:
            forge_config["yum_build_setup"] = yum_build_setup

    forge_config["build_setup"] = _get_build_setup_line(
        forge_dir, platform, forge_config
    )

    template_files = [".circleci/fast_finish_ci_pr_build.sh"]

    if platform == "linux":
        template_files.append(".scripts/run_docker_build.sh")
        template_files.append(".scripts/build_steps.sh")
    else:
        template_files.append(".scripts/run_osx_build.sh")

    _render_template_exe_files(
        forge_config=forge_config,
        jinja_env=jinja_env,
        template_files=template_files,
        forge_dir=forge_dir,
    )

    # Fix permission of other shell files.
    target_fnames = [
        os.path.join(forge_dir, ".circleci", "checkout_merge_commit.sh")
    ]
    for target_fname in target_fnames:
        set_exe_file(target_fname, True)


def generate_yum_requirements(forge_config, forge_dir):
    # If there is a "yum_requirements.txt" file in the recipe, we honour it.
    yum_requirements_fpath = os.path.join(
        forge_dir, forge_config["recipe_dir"], "yum_requirements.txt"
    )
    yum_build_setup = ""
    if os.path.exists(yum_requirements_fpath):
        with open(yum_requirements_fpath) as fh:
            requirements = [
                line.strip()
                for line in fh
                if line.strip() and not line.strip().startswith("#")
            ]
        if not requirements:
            raise ValueError(
                "No yum requirements enabled in the "
                "yum_requirements.txt, please remove the file "
                "or add some."
            )
        yum_build_setup = textwrap.dedent(
            """\

            # Install the yum requirements defined canonically in the
            # "recipe/yum_requirements.txt" file. After updating that file,
            # run "conda smithy rerender" and this line will be updated
            # automatically.
            /usr/bin/sudo -n yum install -y {}


        """.format(
                " ".join(requirements)
            )
        )
    return yum_build_setup


def _get_platforms_of_provider(provider, forge_config):
    platforms = []
    keep_noarchs = []
    archs = []
    upload_packages = []
    for platform_arch in forge_config["build_platform"].keys():
        platform, arch = platform_arch.split("_")
        build_platform_arch = forge_config["build_platform"][platform_arch]
        build_platform, build_arch = build_platform_arch.split("_")
        if (
            build_arch == "64"
            and build_platform in forge_config["provider"]
            and forge_config["provider"][build_platform]
        ):
            build_platform_arch = build_platform

        if build_platform_arch not in forge_config["provider"]:
            continue
        providers = forge_config["provider"][build_platform_arch]
        if provider in providers:
            platforms.append(platform)
            archs.append(arch)
            if platform_arch in forge_config["noarch_platforms"]:
                keep_noarchs.append(True)
            else:
                keep_noarchs.append(False)
            # Allow config to disable package uploads on a per provider basis,
            # default to True if not set explicitly set to False by config entry.
            upload_packages.append(
                forge_config.get(provider, {}).get("upload_packages", True)
            )
        elif (
            provider == "azure"
            and forge_config["azure"]["force"]
            and arch == "64"
        ):
            platforms.append(platform)
            archs.append(arch)
            if platform_arch in forge_config["noarch_platforms"]:
                keep_noarchs.append(True)
            else:
                keep_noarchs.append(False)
            upload_packages.append(False)
    return platforms, archs, keep_noarchs, upload_packages


def render_circle(jinja_env, forge_config, forge_dir, return_metadata=False):
    target_path = os.path.join(forge_dir, ".circleci", "config.yml")
    template_filename = "circle.yml.tmpl"
    fast_finish_text = textwrap.dedent(
        """\
            {get_fast_finish_script} | \\
                 python - -v --ci "circle" "${{CIRCLE_PROJECT_USERNAME}}/${{CIRCLE_PROJECT_REPONAME}}" "${{CIRCLE_BUILD_NUM}}" "${{CIRCLE_PR_NUMBER}}"
        """  # noqa
    )
    extra_platform_files = {
        "common": [
            os.path.join(forge_dir, ".circleci", "checkout_merge_commit.sh"),
            os.path.join(forge_dir, ".circleci", "fast_finish_ci_pr_build.sh"),
        ],
    }

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("circle", forge_config)

    return _render_ci_provider(
        "circle",
        jinja_env=jinja_env,
        forge_config=forge_config,
        forge_dir=forge_dir,
        platforms=platforms,
        archs=archs,
        fast_finish_text=fast_finish_text,
        platform_target_path=target_path,
        platform_template_file=template_filename,
        platform_specific_setup=_circle_specific_setup,
        keep_noarchs=keep_noarchs,
        extra_platform_files=extra_platform_files,
        upload_packages=upload_packages,
        return_metadata=return_metadata,
    )


def _travis_specific_setup(jinja_env, forge_config, forge_dir, platform):
    build_setup = _get_build_setup_line(forge_dir, platform, forge_config)

    platform_templates = {
        "linux": [".scripts/run_docker_build.sh", ".scripts/build_steps.sh"],
        "osx": [".scripts/run_osx_build.sh"],
        "win": [],
    }
    template_files = platform_templates.get(platform, [])

    if platform == "linux":
        yum_build_setup = generate_yum_requirements(forge_config, forge_dir)
        if yum_build_setup:
            forge_config["yum_build_setup"] = yum_build_setup

    forge_config["build_setup"] = build_setup

    _render_template_exe_files(
        forge_config=forge_config,
        jinja_env=jinja_env,
        template_files=template_files,
        forge_dir=forge_dir,
    )


def _render_template_exe_files(
    forge_config, jinja_env, template_files, forge_dir
):
    for template_file in template_files:
        template = jinja_env.get_template(
            os.path.basename(template_file) + ".tmpl"
        )
        target_fname = os.path.join(forge_dir, template_file)
        new_file_contents = template.render(**forge_config)
        if target_fname in get_common_scripts(forge_dir) and os.path.exists(
            target_fname
        ):
            with open(target_fname) as fh:
                old_file_contents = fh.read()
                if old_file_contents != new_file_contents:
                    import difflib

                    diff_text = "\n".join(
                        difflib.unified_diff(
                            old_file_contents.splitlines(),
                            new_file_contents.splitlines(),
                            fromfile=target_fname,
                            tofile=target_fname,
                        )
                    )
                    logger.debug(f"diff:\n{diff_text}")
                    raise RuntimeError(
                        f"Same file {target_fname} is rendered twice with different contents"
                    )
        with write_file(target_fname) as fh:
            fh.write(new_file_contents)
        # Fix permission of template shell files
        set_exe_file(target_fname, True)


def render_travis(jinja_env, forge_config, forge_dir, return_metadata=False):
    target_path = os.path.join(forge_dir, ".travis.yml")
    template_filename = "travis.yml.tmpl"
    fast_finish_text = ""

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("travis", forge_config)

    return _render_ci_provider(
        "travis",
        jinja_env=jinja_env,
        forge_config=forge_config,
        forge_dir=forge_dir,
        platforms=platforms,
        archs=archs,
        fast_finish_text=fast_finish_text,
        platform_target_path=target_path,
        platform_template_file=template_filename,
        keep_noarchs=keep_noarchs,
        platform_specific_setup=_travis_specific_setup,
        upload_packages=upload_packages,
        return_metadata=return_metadata,
    )


def _appveyor_specific_setup(jinja_env, forge_config, forge_dir, platform):
    build_setup = _get_build_setup_line(forge_dir, platform, forge_config)
    build_setup = build_setup.rstrip()
    new_build_setup = ""
    for line in build_setup.split("\n"):
        if line.startswith("#"):
            new_build_setup += "    " + line + "\n"
        else:
            new_build_setup += "    - cmd: " + line + "\n"
    build_setup = new_build_setup.strip()

    forge_config["build_setup"] = build_setup


def render_appveyor(jinja_env, forge_config, forge_dir, return_metadata=False):
    target_path = os.path.join(forge_dir, ".appveyor.yml")
    fast_finish_text = textwrap.dedent(
        """\
            {get_fast_finish_script}
            "%CONDA_INSTALL_LOCN%\\python.exe" {fast_finish_script}.py -v --ci "appveyor" "%APPVEYOR_ACCOUNT_NAME%/%APPVEYOR_PROJECT_SLUG%" "%APPVEYOR_BUILD_NUMBER%" "%APPVEYOR_PULL_REQUEST_NUMBER%"
        """  # noqa
    )
    template_filename = "appveyor.yml.tmpl"

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("appveyor", forge_config)

    return _render_ci_provider(
        "appveyor",
        jinja_env=jinja_env,
        forge_config=forge_config,
        forge_dir=forge_dir,
        platforms=platforms,
        archs=archs,
        fast_finish_text=fast_finish_text,
        platform_target_path=target_path,
        platform_template_file=template_filename,
        keep_noarchs=keep_noarchs,
        platform_specific_setup=_appveyor_specific_setup,
        upload_packages=upload_packages,
        return_metadata=return_metadata,
    )


def _github_actions_specific_setup(
    jinja_env, forge_config, forge_dir, platform
):
    # Handle GH-hosted and self-hosted runners runs-on config
    # Do it before the deepcopy below so these changes can be used by the
    # .github/worfkflows/conda-build.yml template
    runs_on = {
        "osx-64": {
            "os": "macos",
            "hosted_labels": ("macos-13",),
            "self_hosted_labels": ("macOS", "x64"),
        },
        "osx-arm64": {
            "os": "macos",
            # FUTURE: Use -latest once GHA fully migrates
            "hosted_labels": ("macos-14",),
            "self_hosted_labels": ("macOS", "arm64"),
        },
        "linux-64": {
            "os": "ubuntu",
            "hosted_labels": ("ubuntu-latest",),
            "self_hosted_labels": ("linux", "x64"),
        },
        "linux-aarch64": {
            "os": "ubuntu",
            "hosted_labels": ("ubuntu-latest",),
            "self_hosted_labels": ("linux", "ARM64"),
        },
        "win-64": {
            "os": "windows",
            "hosted_labels": ("windows-latest",),
            "self_hosted_labels": ("windows", "x64"),
        },
        "win-arm64": {
            "os": "windows",
            "hosted_labels": ("windows-latest",),
            "self_hosted_labels": ("windows", "ARM64"),
        },
    }
    for data in forge_config["configs"]:
        if not data["build_platform"].startswith(platform):
            continue
        # This Github Actions specific configs are prefixed with "gha_"
        # because we are not deepcopying the data dict intentionally
        # so it can be used in the general "render_github_actions" function
        # This avoid potential collisions with other CI providers :crossed_fingers:
        data["gha_os"] = runs_on[data["build_platform"]]["os"]
        data["gha_with_gpu"] = False

        self_hosted_default = list(
            runs_on[data["build_platform"]]["self_hosted_labels"]
        )
        self_hosted_default += ["self-hosted"]
        hosted_default = list(runs_on[data["build_platform"]]["hosted_labels"])

        labels_default = (
            ["self-hosted"]
            if forge_config["github_actions"]["self_hosted"]
            else ["hosted"]
        )
        labels = conda_build.utils.ensure_list(
            data["config"].get("github_actions_labels", [labels_default])[0]
        )

        if len(labels) == 1 and labels[0] == "hosted":
            labels = hosted_default
        elif len(labels) == 1 and labels[0] in "self-hosted":
            labels = self_hosted_default
        else:
            # Prepend the required ones
            labels += self_hosted_default

        if forge_config["github_actions"]["self_hosted"]:
            data["gha_runs_on"] = []
            # labels provided in conda-forge.yml
            for label in labels:
                if label.startswith("cirun-"):
                    label += (
                        "--${{ github.run_id }}-" + data["short_config_name"]
                    )
                if "gpu" in label.lower():
                    data["gha_with_gpu"] = True
                data["gha_runs_on"].append(label)
        else:
            data["gha_runs_on"] = hosted_default

    build_setup = _get_build_setup_line(forge_dir, platform, forge_config)

    if platform == "linux":
        yum_build_setup = generate_yum_requirements(forge_config, forge_dir)
        if yum_build_setup:
            forge_config["yum_build_setup"] = yum_build_setup

    forge_config = deepcopy(forge_config)
    forge_config["build_setup"] = build_setup

    platform_templates = {
        "linux": [
            ".scripts/run_docker_build.sh",
            ".scripts/build_steps.sh",
        ],
        "osx": [
            ".scripts/run_osx_build.sh",
        ],
        "win": [
            ".scripts/run_win_build.bat",
        ],
    }

    template_files = platform_templates.get(platform, [])

    # Templates for all platforms
    if forge_config["github_actions"]["store_build_artifacts"]:
        template_files.append(".scripts/create_conda_build_artifacts.sh")

    _render_template_exe_files(
        forge_config=forge_config,
        jinja_env=jinja_env,
        template_files=template_files,
        forge_dir=forge_dir,
    )


def render_github_actions(
    jinja_env, forge_config, forge_dir, return_metadata=False
):
    target_path = os.path.join(
        forge_dir, ".github", "workflows", "conda-build.yml"
    )
    template_filename = "github-actions.yml.tmpl"
    fast_finish_text = ""

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("github_actions", forge_config)

    logger.debug("github platforms retrieved")

    remove_file_or_dir(target_path)
    return _render_ci_provider(
        "github_actions",
        jinja_env=jinja_env,
        forge_config=forge_config,
        forge_dir=forge_dir,
        platforms=platforms,
        archs=archs,
        fast_finish_text=fast_finish_text,
        platform_target_path=target_path,
        platform_template_file=template_filename,
        platform_specific_setup=_github_actions_specific_setup,
        keep_noarchs=keep_noarchs,
        upload_packages=upload_packages,
        return_metadata=return_metadata,
    )


def _azure_specific_setup(jinja_env, forge_config, forge_dir, platform):
    build_setup = _get_build_setup_line(forge_dir, platform, forge_config)

    if platform == "linux":
        yum_build_setup = generate_yum_requirements(forge_config, forge_dir)
        if yum_build_setup:
            forge_config["yum_build_setup"] = yum_build_setup

    forge_config = deepcopy(forge_config)
    forge_config["build_setup"] = build_setup

    platform_templates = {
        "linux": [
            ".scripts/run_docker_build.sh",
            ".scripts/build_steps.sh",
            ".azure-pipelines/azure-pipelines-linux.yml",
        ],
        "osx": [
            ".azure-pipelines/azure-pipelines-osx.yml",
            ".scripts/run_osx_build.sh",
        ],
        "win": [
            ".azure-pipelines/azure-pipelines-win.yml",
            ".scripts/run_win_build.bat",
        ],
    }
    if forge_config["azure"]["store_build_artifacts"]:
        platform_templates["linux"].append(
            ".scripts/create_conda_build_artifacts.sh"
        )
        platform_templates["osx"].append(
            ".scripts/create_conda_build_artifacts.sh"
        )
        platform_templates["win"].append(
            ".scripts/create_conda_build_artifacts.bat"
        )
    template_files = platform_templates.get(platform, [])

    azure_settings = deepcopy(forge_config["azure"][f"settings_{platform}"])
    azure_settings.pop("swapfile_size", None)
    azure_settings.setdefault("strategy", {})
    azure_settings["strategy"].setdefault("matrix", {})

    # Limit the amount of parallel jobs running at the same time
    # weighted by platform population
    max_parallel = forge_config["azure"]["max_parallel"]
    if len(forge_config["configs"]) > max_parallel:
        n_configs = len(forge_config["configs"])
        platform_counts = Counter(
            [
                k["build_platform"].split("-")[0]
                for k in forge_config["configs"]
            ]
        )
        ratio = platform_counts[platform.split("-")[0]] / n_configs
        azure_settings["strategy"]["maxParallel"] = max(
            1, round(max_parallel * ratio)
        )

    for data in forge_config["configs"]:
        if not data["build_platform"].startswith(platform):
            continue
        config_rendered = OrderedDict(
            {
                "CONFIG": data["config_name"],
                "UPLOAD_PACKAGES": str(data["upload"]),
            }
        )
        # fmt: off
        if "docker_image" in data["config"] and platform == "linux":
            config_rendered["DOCKER_IMAGE"] = data["config"]["docker_image"][-1]
        if forge_config["azure"]["store_build_artifacts"]:
            config_rendered["SHORT_CONFIG"] = data["short_config_name"]
        azure_settings["strategy"]["matrix"][data["config_name"]] = config_rendered
        # fmt: on

    forge_config["azure_yaml"] = yaml.dump(azure_settings)
    _render_template_exe_files(
        forge_config=forge_config,
        jinja_env=jinja_env,
        template_files=template_files,
        forge_dir=forge_dir,
    )


def render_azure(jinja_env, forge_config, forge_dir, return_metadata=False):
    target_path = os.path.join(forge_dir, "azure-pipelines.yml")
    template_filename = "azure-pipelines.yml.tmpl"
    fast_finish_text = ""

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("azure", forge_config)

    logger.debug("azure platforms retreived")

    remove_file_or_dir(os.path.join(forge_dir, ".azure-pipelines"))
    return _render_ci_provider(
        "azure",
        jinja_env=jinja_env,
        forge_config=forge_config,
        forge_dir=forge_dir,
        platforms=platforms,
        archs=archs,
        fast_finish_text=fast_finish_text,
        platform_target_path=target_path,
        platform_template_file=template_filename,
        platform_specific_setup=_azure_specific_setup,
        keep_noarchs=keep_noarchs,
        upload_packages=upload_packages,
        return_metadata=return_metadata,
    )


def _drone_specific_setup(jinja_env, forge_config, forge_dir, platform):
    platform_templates = {
        "linux": [".scripts/build_steps.sh"],
        "osx": [],
        "win": [],
    }
    template_files = platform_templates.get(platform, [])

    build_setup = _get_build_setup_line(forge_dir, platform, forge_config)

    if platform == "linux":
        yum_build_setup = generate_yum_requirements(forge_config, forge_dir)
        if yum_build_setup:
            forge_config["yum_build_setup"] = yum_build_setup

    forge_config["build_setup"] = build_setup

    _render_template_exe_files(
        forge_config=forge_config,
        jinja_env=jinja_env,
        template_files=template_files,
        forge_dir=forge_dir,
    )


def render_drone(jinja_env, forge_config, forge_dir, return_metadata=False):
    target_path = os.path.join(forge_dir, ".drone.yml")
    template_filename = "drone.yml.tmpl"
    fast_finish_text = ""

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("drone", forge_config)

    return _render_ci_provider(
        "drone",
        jinja_env=jinja_env,
        forge_config=forge_config,
        forge_dir=forge_dir,
        platforms=platforms,
        archs=archs,
        fast_finish_text=fast_finish_text,
        platform_target_path=target_path,
        platform_template_file=template_filename,
        platform_specific_setup=_drone_specific_setup,
        keep_noarchs=keep_noarchs,
        upload_packages=upload_packages,
        return_metadata=return_metadata,
    )


_woodpecker_specific_setup = _drone_specific_setup


def render_woodpecker(
    jinja_env, forge_config, forge_dir, return_metadata=False
):
    target_path = os.path.join(forge_dir, ".woodpecker.yml")
    template_filename = "woodpecker.yml.tmpl"
    fast_finish_text = ""

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("woodpecker", forge_config)

    return _render_ci_provider(
        "woodpecker",
        jinja_env=jinja_env,
        forge_config=forge_config,
        forge_dir=forge_dir,
        platforms=platforms,
        archs=archs,
        fast_finish_text=fast_finish_text,
        platform_target_path=target_path,
        platform_template_file=template_filename,
        platform_specific_setup=_woodpecker_specific_setup,
        keep_noarchs=keep_noarchs,
        upload_packages=upload_packages,
        return_metadata=return_metadata,
    )


def azure_build_id_from_token(forge_config):
    """Retrieve Azure `build_id` from a `forge_config` using an Azure token.
    This function allows the `build_id` to be retrieved when the Azure org is private.
    """
    # If it fails then we switch to a request using an Azure token.
    from conda_smithy import azure_ci_utils

    config = azure_ci_utils.AzureConfig(
        org_or_user=forge_config["azure"]["user_or_org"],
        project_name=forge_config["azure"]["project_name"],
    )
    repo = forge_config["github"]["repo_name"]
    build_info = azure_ci_utils.get_build_id(repo, config)
    forge_config["azure"]["build_id"] = build_info["build_id"]


def azure_build_id_from_public(forge_config):
    """Retrieve Azure `build_id` from a `forge_config`. This function only works
    when the Azure org is public.
    """
    resp = requests.get(
        "https://dev.azure.com/{org}/{project_name}/_apis/build/definitions?name={repo}".format(
            org=forge_config["azure"]["user_or_org"],
            project_name=forge_config["azure"]["project_name"],
            repo=forge_config["github"]["repo_name"],
        )
    )
    resp.raise_for_status()
    build_def = resp.json()["value"][0]
    forge_config["azure"]["build_id"] = build_def["id"]


def render_readme(jinja_env, forge_config, forge_dir, render_info=None):
    if "README.md" in forge_config["skip_render"]:
        logger.info("README.md rendering is skipped")
        return

    render_info = render_info or []
    metas = []
    for md in render_info:
        for _metas, enabled in zip(
            md["metas_list_of_lists"], md["enable_platform"]
        ):
            if enabled and len(_metas) > 0:
                metas.extend(_metas)

    if len(metas) == 0:
        try:
            metas = conda_build.api.render(
                os.path.join(forge_dir, forge_config["recipe_dir"]),
                exclusive_config_file=forge_config["exclusive_config_file"],
                permit_undefined_jinja=True,
                finalize=False,
                bypass_env_check=True,
                trim_skip=False,
            )
            metas = [m[0] for m in metas]
        except Exception:
            raise RuntimeError(
                "Could not create any metadata for rendering the README.md!"
                " This likely indicates a serious bug or a feedstock with no actual"
                " builds."
            )

    package_name = get_feedstock_name_from_meta(metas[0])
    package_about = get_feedstock_about_from_meta(metas[0])

    ci_support_path = os.path.join(forge_dir, ".ci_support")
    variants = []
    channel_targets = []
    if os.path.exists(ci_support_path):
        for filename in os.listdir(ci_support_path):
            if filename.endswith(".yaml"):
                variant_name, _ = os.path.splitext(filename)
                variants.append(variant_name)
                with open(os.path.join(ci_support_path, filename)) as fh:
                    data = yaml.safe_load(fh)
                    channel_targets.append(
                        data.get("channel_targets", ["conda-forge main"])[0]
                    )

    if not channel_targets:
        # default to conda-forge if no channel_targets are specified (shouldn't happen)
        channel_targets = ["conda-forge main"]

    subpackages_metas = OrderedDict((meta.name(), meta) for meta in metas)
    subpackages_about = [(package_name, package_about)]
    for name, m in subpackages_metas.items():
        about = m.meta["about"]
        if isinstance(about, list):
            about = about[0]
        about = about.copy()
        # if subpackages do not have about, conda-build would copy the top-level about;
        # if subpackages have their own about, conda-build would use them as is;
        # we discussed in PR #1691 and decided to not show repetitve entries
        if about != package_about:
            subpackages_about.append((name, about))

    template = jinja_env.get_template("README.md.tmpl")
    target_fname = os.path.join(forge_dir, "README.md")
    forge_config["noarch_python"] = all(meta.noarch for meta in metas)
    forge_config["package_about"] = subpackages_about
    forge_config["package_name"] = package_name
    forge_config["variants"] = sorted(variants)
    forge_config["outputs"] = sorted(
        list(OrderedDict((meta.name(), None) for meta in metas))
    )
    forge_config["maintainers"] = sorted(
        set(
            chain.from_iterable(
                meta.meta["extra"].get("recipe-maintainers", [])
                for meta in metas
            )
        )
    )
    forge_config["channel_targets"] = channel_targets

    if forge_config["azure"].get("build_id") is None:
        # Try to retrieve the build_id from the interwebs.
        # Works if the Azure CI is public
        try:
            azure_build_id_from_public(forge_config)
        except (OSError, IndexError) as err:
            # We don't want to command to fail if requesting the build_id fails.
            logger.warning(
                f"Azure build_id can't be retrieved using the Azure token. Exception: {err}"
            )
        except json.decoder.JSONDecodeError:
            azure_build_id_from_token(forge_config)

    logger.debug("README")
    logger.debug(yaml.dump(forge_config))

    with write_file(target_fname) as fh:
        fh.write(template.render(**forge_config))

    code_owners_file = os.path.join(forge_dir, ".github", "CODEOWNERS")
    if len(forge_config["maintainers"]) > 0:
        with write_file(code_owners_file) as fh:
            line = "*"
            for maintainer in forge_config["maintainers"]:
                if "/" in maintainer:
                    _maintainer = maintainer.lower()
                else:
                    _maintainer = maintainer
                line = line + " @" + _maintainer
            fh.write(line)
    else:
        remove_file_or_dir(code_owners_file)


def _get_skip_files(forge_config):
    skip_files = {"README", "__pycache__"}
    for f in forge_config["skip_render"]:
        skip_files.add(f)
    return skip_files


def render_github_actions_services(jinja_env, forge_config, forge_dir):
    # render github actions files for automerge and rerendering services
    skip_files = _get_skip_files(forge_config)
    for template_file in ["automerge.yml", "webservices.yml"]:
        template = jinja_env.get_template(template_file + ".tmpl")
        rel_target_fname = os.path.join(".github", "workflows", template_file)
        if _ignore_match(skip_files, rel_target_fname):
            continue
        target_fname = os.path.join(forge_dir, rel_target_fname)
        new_file_contents = template.render(**forge_config)
        with write_file(target_fname) as fh:
            fh.write(new_file_contents)


def copy_feedstock_content(forge_config, forge_dir):
    feedstock_content = os.path.join(conda_forge_content, "feedstock_content")
    skip_files = _get_skip_files(forge_config)
    copytree(feedstock_content, forge_dir, skip_files)


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

    if file_config.get("docker") and file_config.get("docker").get("image"):
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


def get_most_recent_version(name, include_broken=False):
    request = requests.get(
        "https://api.anaconda.org/package/conda-forge/" + name
    )
    request.raise_for_status()
    files = request.json()["files"]
    if not include_broken:
        files = [f for f in files if "broken" not in f.get("labels", ())]
    pkg = max(files, key=lambda x: VersionOrder(x["version"]))

    PackageRecord = namedtuple("PackageRecord", ["name", "version", "url"])
    return PackageRecord(name, pkg["version"], "https:" + pkg["download_url"])


def check_version_uptodate(name, installed_version, error_on_warn):
    most_recent_version = get_most_recent_version(name).version
    if installed_version is None:
        msg = f"{name} is not installed in conda-smithy's environment."
    elif VersionOrder(installed_version) < VersionOrder(most_recent_version):
        msg = f"{name} version ({installed_version}) is out-of-date ({most_recent_version}) in conda-smithy's environment."
    else:
        return
    if error_on_warn:
        raise RuntimeError(f"{msg} Exiting.")
    else:
        logger.info(msg)


def commit_changes(forge_file_directory, commit, cs_ver, cfp_ver, cb_ver):
    if cfp_ver:
        msg = f"Re-rendered with conda-build {cb_ver}, conda-smithy {cs_ver}, and conda-forge-pinning {cfp_ver}"
    else:
        msg = (
            f"Re-rendered with conda-build {cb_ver} and conda-smithy {cs_ver}"
        )
    logger.info(msg)

    is_git_repo = os.path.exists(os.path.join(forge_file_directory, ".git"))
    if is_git_repo:
        has_staged_changes = subprocess.call(
            ["git", "diff", "--cached", "--quiet", "--exit-code"],
            cwd=forge_file_directory,
        )
        if has_staged_changes:
            if commit:
                git_args = ["git", "commit", "-m", f"MNT: {msg}"]
                if commit == "edit":
                    git_args += ["--edit", "--status", "--verbose"]
                subprocess.check_call(git_args, cwd=forge_file_directory)
                logger.info("")
            else:
                logger.info(
                    "You can commit the changes with:\n\n"
                    f'    git commit -m "MNT: {msg}"\n'
                )
            logger.info("These changes need to be pushed to github!\n")
        else:
            logger.info("No changes made. This feedstock is up-to-date.\n")


def get_cfp_file_path(temporary_directory):
    pkg = get_most_recent_version("conda-forge-pinning")
    if pkg.url.endswith(".conda"):
        ext = ".conda"
    elif pkg.url.endswith(".tar.bz2"):
        ext = ".tar.bz2"
    else:
        raise RuntimeError(
            "Could not determine proper conda package extension for "
            f"pinning package '{pkg.url}'!"
        )
    dest = os.path.join(
        temporary_directory, f"conda-forge-pinning-{ pkg.version }{ext}"
    )

    logger.info(f"Downloading conda-forge-pinning-{ pkg.version }")

    response = requests.get(pkg.url)
    response.raise_for_status()
    with open(dest, "wb") as f:
        f.write(response.content)

    logger.info(f"Extracting conda-forge-pinning to { temporary_directory }")
    cmd = ["cph"]
    # If possible, avoid needing to activate the environment to access cph
    if sys.executable:
        cmd = [sys.executable, "-m", "conda_package_handling.cli"]
    cmd += ["x", "--dest", temporary_directory, dest]
    subprocess.check_call(cmd)

    logger.debug(os.listdir(temporary_directory))

    cf_pinning_file = os.path.join(
        temporary_directory, "conda_build_config.yaml"
    )
    cf_pinning_ver = pkg.version

    assert os.path.exists(cf_pinning_file)

    return cf_pinning_file, cf_pinning_ver


def get_cache_dir():
    if sys.platform.startswith("win"):
        return Path(os.environ.get("TEMP"))
    else:
        return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))


def get_cached_cfp_file_path(temporary_directory):
    if cache_dir := get_cache_dir():
        smithy_cache = cache_dir / "conda-smithy"
        smithy_cache.mkdir(parents=True, exist_ok=True)
        pinning_version = None
        # Do we already have the pinning cached?
        if (smithy_cache / "conda-forge-pinng-version").exists():
            pinning_version = (
                smithy_cache / "conda-forge-pinng-version"
            ).read_text()

        # Check whether we have recently already updated the cache
        current_ts = int(time.time())
        if (smithy_cache / "conda-forge-pinng-version-ts").exists():
            last_ts = int(
                (smithy_cache / "conda-forge-pinng-version-ts").read_text()
            )
        else:
            last_ts = 0

        if current_ts - last_ts > CONDA_FORGE_PINNING_LIFETIME:
            current_pinning_version = get_most_recent_version(
                "conda-forge-pinning"
            ).version
            (smithy_cache / "conda-forge-pinng-version-ts").write_text(
                str(current_ts)
            )
            if current_pinning_version != pinning_version:
                get_cfp_file_path(smithy_cache)
                (smithy_cache / "conda-forge-pinng-version").write_text(
                    current_pinning_version
                )
                pinning_version = current_pinning_version

        return str(smithy_cache / "conda_build_config.yaml"), pinning_version
    else:
        return get_cfp_file_path(temporary_directory)


def clear_variants(forge_dir):
    "Remove all variant files placed in the .ci_support path"
    if os.path.isdir(os.path.join(forge_dir, ".ci_support")):
        configs = glob.glob(os.path.join(forge_dir, ".ci_support", "*.yaml"))
        for config in configs:
            remove_file(config)


def get_common_scripts(forge_dir):
    for old_file in [
        "run_docker_build.sh",
        "build_steps.sh",
        "run_osx_build.sh",
        "create_conda_build_artifacts.bat",
        "create_conda_build_artifacts.sh",
    ]:
        yield os.path.join(forge_dir, ".scripts", old_file)


def clear_scripts(forge_dir):
    for folder in [
        ".azure-pipelines",
        ".circleci",
        ".drone",
        ".travis",
        ".scripts",
    ]:
        for old_file in [
            "run_docker_build.sh",
            "build_steps.sh",
            "run_osx_build.sh",
            "run_win_build.bat",
            "create_conda_build_artifacts.bat",
            "create_conda_build_artifacts.sh",
        ]:
            remove_file(os.path.join(forge_dir, folder, old_file))


def make_jinja_env(feedstock_directory):
    """Creates a Jinja environment usable for rendering templates"""
    forge_dir = os.path.abspath(feedstock_directory)
    tmplt_dir = os.path.join(conda_forge_content, "templates")
    # Load templates from the feedstock in preference to the smithy's templates.
    env = SandboxedEnvironment(
        extensions=["jinja2.ext.do"],
        loader=FileSystemLoader(
            [os.path.join(forge_dir, "templates"), tmplt_dir]
        ),
    )
    return env


def get_migrations_in_dir(migrations_root):
    """
    Given a directory, return the migrations as a mapping
    from the timestamp to a tuple of (filename, migration_number)
    """
    res = {}
    for fn in glob.glob(os.path.join(migrations_root, "*.yaml")):
        with open(fn) as f:
            contents = f.read()
            migration_yaml = (
                yaml.load(contents, Loader=yaml.loader.BaseLoader) or {}
            )
            # Use a object as timestamp to not delete it
            ts = migration_yaml.get("migrator_ts", object())
            migration_number = migration_yaml.get("__migrator", {}).get(
                "migration_number", 1
            )
            use_local = (
                migration_yaml.get("__migrator", {})
                .get("use_local", "false")
                .lower()
                == "true"
            )
            res[ts] = (fn, migration_number, use_local)
    return res


def set_migration_fns(forge_dir, forge_config):
    """
    This will calculate the migration files and set migration_fns
    in the forge_config as a list.

    First, this will look in the conda-forge-pinning (CFP) package
    to see if it has migrations installed. If not, the filenames of
    the migrations the feedstock are used.

    Then, this will look at migrations in the feedstock and if they
    have a timestamp and doesn't exist in the CFP package, the
    migration is considered old and deleted.

    Then, if there is a migration in the feedstock with the same
    migration number and timestamp in the CFP package, the filename of
    the migration in the CFP package is used.

    Finally, if none of the conditions are met for a migration in the
    feedstock, the filename of the migration in the feedstock is used.
    """
    exclusive_config_file = forge_config["exclusive_config_file"]
    cfp_migrations_dir = os.path.join(
        os.path.dirname(exclusive_config_file),
        "share",
        "conda-forge",
        "migrations",
    )

    migrations_root = os.path.join(forge_dir, ".ci_support", "migrations")
    migrations_in_feedstock = get_migrations_in_dir(migrations_root)

    if not os.path.exists(cfp_migrations_dir):
        migration_fns = [fn for fn, _, _ in migrations_in_feedstock.values()]
        forge_config["migration_fns"] = migration_fns
        return

    migrations_in_cfp = get_migrations_in_dir(cfp_migrations_dir)

    result = []
    for ts, (fn, num, use_local) in migrations_in_feedstock.items():
        if use_local or not isinstance(ts, (int, str, float)):
            # This file has a setting to use the file in the feedstock
            # or doesn't have a timestamp. Use it as it is.
            result.append(fn)
        elif ts in migrations_in_cfp:
            # Use the one from cfp if migration_numbers match
            new_fn, new_num, _ = migrations_in_cfp[ts]
            if num == new_num:
                logger.info(
                    f"{os.path.basename(fn)} from feedstock is ignored and upstream version is used"
                )
                result.append(new_fn)
            else:
                result.append(fn)
        else:
            # Delete this as this migration is over.
            logger.info(f"{os.path.basename(fn)} is closed now. Removing")
            remove_file(fn)
    forge_config["migration_fns"] = result
    return


def main(
    forge_file_directory,
    forge_yml=None,
    no_check_uptodate=False,
    commit=False,
    exclusive_config_file=None,
    check=False,
    temporary_directory=None,
):
    loglevel = os.environ.get("CONDA_SMITHY_LOGLEVEL", "INFO").upper()
    logger.setLevel(loglevel)

    if check or not no_check_uptodate:
        # Check that conda-smithy is up-to-date
        check_version_uptodate("conda-smithy", __version__, True)
        if check:
            return True

    forge_dir = os.path.abspath(forge_file_directory)

    if exclusive_config_file is not None:
        exclusive_config_file = os.path.join(forge_dir, exclusive_config_file)
        if not os.path.exists(exclusive_config_file):
            raise RuntimeError("Given exclusive-config-file not found.")
        cf_pinning_ver = None

    else:
        exclusive_config_file, cf_pinning_ver = get_cached_cfp_file_path(
            temporary_directory
        )

    config = _load_forge_config(forge_dir, exclusive_config_file, forge_yml)

    config["feedstock_name"] = os.path.basename(forge_dir)

    env = make_jinja_env(forge_dir)
    logger.debug("env rendered")

    copy_feedstock_content(config, forge_dir)

    if os.path.exists(os.path.join(forge_dir, "build-locally.py")):
        set_exe_file(os.path.join(forge_dir, "build-locally.py"))

    clear_variants(forge_dir)
    clear_scripts(forge_dir)
    set_migration_fns(forge_dir, config)

    logger.debug("migration fns set")

    # the order of these calls appears to matter
    render_info = []
    render_info.append(
        render_circle(env, config, forge_dir, return_metadata=True)
    )

    logger.debug("circle rendered")
    render_info.append(
        render_travis(env, config, forge_dir, return_metadata=True)
    )

    logger.debug("travis rendered")
    render_info.append(
        render_appveyor(env, config, forge_dir, return_metadata=True)
    )

    logger.debug("appveyor rendered")
    render_info.append(
        render_azure(env, config, forge_dir, return_metadata=True)
    )

    logger.debug("azure rendered")
    render_info.append(
        render_drone(env, config, forge_dir, return_metadata=True)
    )

    logger.debug("drone rendered")
    render_info.append(
        render_woodpecker(env, config, forge_dir, return_metadata=True)
    )

    logger.debug("woodpecker rendered")
    render_info.append(
        render_github_actions(env, config, forge_dir, return_metadata=True)
    )

    logger.debug("github_actions rendered")
    render_github_actions_services(env, config, forge_dir)

    logger.debug("github_actions services rendered")

    # put azure first just in case
    azure_ind = ([ri["provider_name"] for ri in render_info]).index("azure")
    tmp = render_info[0]
    render_info[0] = render_info[azure_ind]
    render_info[azure_ind] = tmp
    render_readme(env, config, forge_dir, render_info)

    logger.debug("README rendered")

    commit_changes(
        forge_file_directory,
        commit,
        __version__,
        cf_pinning_ver,
        conda_build_version,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Configure a feedstock given a conda-forge.yml file."
    )
    parser.add_argument(
        "forge_file_directory",
        help=(
            "the directory containing the conda-forge.yml file "
            "used to configure the feedstock"
        ),
    )

    args = parser.parse_args()
    main(args.forge_file_directory)
