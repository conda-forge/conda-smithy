import glob
from itertools import product, chain
import logging
import os
import subprocess
import textwrap
import yaml
import warnings
from collections import OrderedDict
import copy

import conda_build.api
import conda_build.utils
import conda_build.variants
import conda_build.conda_interface
import conda_build.render

from copy import deepcopy

from conda_build import __version__ as conda_build_version
from jinja2 import Environment, FileSystemLoader

from conda_smithy.feedstock_io import (
    set_exe_file,
    write_file,
    remove_file,
    copy_file,
    remove_file_or_dir,
)
from . import __version__

conda_forge_content = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger(__name__)


def package_key(config, used_loop_vars, subdir):
    # get the build string from whatever conda-build makes of the configuration
    build_vars = "".join(
        [k + str(config[k][0]) for k in sorted(list(used_loop_vars))]
    )
    key = []
    # kind of a special case.  Target platform determines a lot of output behavior, but may not be
    #    explicitly listed in the recipe.
    tp = config.get("target_platform")
    if tp and isinstance(tp, list):
        tp = tp[0]
    if tp and tp != subdir and "target_platform" not in build_vars:
        build_vars += "target-" + tp
    if build_vars:
        key.append(build_vars)
    key = "-".join(key)
    return key


def copytree(src, dst, ignore=(), root_dst=None):
    """This emulates shutil.copytree, but does so with our git file tracking, so that the new files
    are added to the repo"""
    if root_dst is None:
        root_dst = dst
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.relpath(d, root_dst) in ignore:
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


def _collapse_subpackage_variants(list_of_metas, root_path):
    """Collapse all subpackage node variants into one aggregate collection of used variables

    We get one node per output, but a given recipe can have multiple outputs.  Each output
    can have its own used_vars, and we must unify all of the used variables for all of the
    outputs"""

    # things we consider "top-level" are things that we loop over with CI jobs.  We don't loop over
    #     outputs with CI jobs.
    top_level_loop_vars = set()

    all_used_vars = set()
    all_variants = set()

    for meta in list_of_metas:
        all_used_vars.update(meta.get_used_vars())
        all_variants.update(
            conda_build.utils.HashableDict(v) for v in meta.config.variants
        )

        all_variants.add(conda_build.utils.HashableDict(meta.config.variant))

    top_level_loop_vars = list_of_metas[0].get_used_loop_vars(
        force_top_level=True
    )
    top_level_vars = list_of_metas[0].get_used_vars(force_top_level=True)
    if "target_platform" in all_used_vars:
        top_level_loop_vars.add("target_platform")

    # this is the initial collection of all variants before we discard any.  "Squishing"
    #     them is necessary because the input form is already broken out into one matrix
    #     configuration per item, and we want a single dict, with each key representing many values
    squished_input_variants = conda_build.variants.list_of_dicts_to_dict_of_lists(
        list_of_metas[0].config.input_variants
    )
    squished_used_variants = conda_build.variants.list_of_dicts_to_dict_of_lists(
        list(all_variants)
    )

    # these are variables that only occur in the top level, and thus won't show up as loops in the
    #     above collection of all variants.  We need to transfer them from the input_variants.
    preserve_top_level_loops = set(top_level_loop_vars) - set(all_used_vars)

    # Add in some variables that should always be preserved
    always_keep_keys = {
        "zip_keys",
        "pin_run_as_build",
        "MACOSX_DEPLOYMENT_TARGET",
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
    all_used_vars.update(always_keep_keys)
    all_used_vars.update(top_level_vars)

    used_key_values = {
        key: squished_input_variants[key]
        for key in all_used_vars
        if key in squished_input_variants
    }

    for k, v in squished_used_variants.items():
        if k in all_used_vars:
            used_key_values[k] = v

    for k in preserve_top_level_loops:
        used_key_values[k] = squished_input_variants[k]

    _trim_unused_zip_keys(used_key_values)
    _trim_unused_pin_run_as_build(used_key_values)

    # to deduplicate potentially zipped keys, we blow out the collection of variables, then
    #     do a set operation, then collapse it again

    used_key_values = conda_build.variants.dict_of_lists_to_list_of_dicts(
        used_key_values,
        extend_keys={
            "zip_keys",
            "pin_run_as_build",
            "ignore_version",
            "ignore_build_only_deps",
        },
    )
    used_key_values = {
        conda_build.utils.HashableDict(variant) for variant in used_key_values
    }
    used_key_values = conda_build.variants.list_of_dicts_to_dict_of_lists(
        list(used_key_values)
    )

    _trim_unused_zip_keys(used_key_values)
    _trim_unused_pin_run_as_build(used_key_values)

    logger.debug("top_level_loop_vars {}".format(top_level_loop_vars))
    logger.debug("used_key_values {}".format(used_key_values))

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


def finalize_config(config, platform, forge_config):
    """For configs without essential parameters like docker_image
    add fallback value.
    """
    if platform.startswith("linux"):
        if "docker_image" in config:
            config["docker_image"] = [config["docker_image"][0]]
        else:
            config["docker_image"] = [forge_config["docker"]["fallback_image"]]
    return config


def dump_subspace_config_files(
    metas, root_path, platform, arch, upload, forge_config
):
    """With conda-build 3, it handles the build matrix.  We take what it spits out, and write a
    config.yaml file for each matrix entry that it spits out.  References to a specific file
    replace all of the old environment variables that specified a matrix entry."""

    # identify how to break up the complete set of used variables.  Anything considered
    #     "top-level" should be broken up into a separate CI job.

    configs, top_level_loop_vars = _collapse_subpackage_variants(
        metas, root_path
    )

    # get rid of the special object notation in the yaml file for objects that we dump
    yaml.add_representer(set, yaml.representer.SafeRepresenter.represent_list)
    yaml.add_representer(
        tuple, yaml.representer.SafeRepresenter.represent_list
    )
    yaml.add_representer(OrderedDict, _yaml_represent_ordereddict)

    platform_arch = "{}-{}".format(platform, arch)
    if arch == "64":
        filename_arch = platform
    else:
        filename_arch = f"{platform}_{arch}"

    output_name = platform if arch == "64" else platform_arch

    result = []
    for config in configs:
        config_name = "{}_{}".format(
            filename_arch,
            package_key(config, top_level_loop_vars, metas[0].config.subdir),
        )
        out_folder = os.path.join(root_path, ".ci_support")
        out_path = os.path.join(out_folder, config_name) + ".yaml"
        if not os.path.isdir(out_folder):
            os.makedirs(out_folder)

        config = finalize_config(config, platform, forge_config)

        with write_file(out_path) as f:
            yaml.dump(config, f, default_flow_style=False)

        target_platform = config.get("target_platform", [platform_arch])[0]
        result.append((config_name, target_platform, upload, config))
    return sorted(result)


def _get_fast_finish_script(
    provider_name, forge_config, forge_dir, fast_finish_text
):
    get_fast_finish_script = ""
    fast_finish_script = ""
    tooling_branch = "master"

    cfbs_fpath = os.path.join(forge_dir, "recipe", "ff_ci_pr_build.py")
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
            get_fast_finish_script += "cat {recipe_dir}/ff_ci_pr_build.py".format(
                recipe_dir=forge_config["recipe_dir"]
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


def migrate_combined_spec(combined_spec, forge_dir, config):
    """CFEP-9 variant migrations

    Apply the list of migrations configurations to the build (in the correct sequence)
    This will be used to change the variant within the list of MetaData instances,
    and return the migrated variants.

    This has to happend before the final variant files are computed.

    The method for application is determined by the variant algebra as defined by CFEP-9

    """
    combined_spec = combined_spec.copy()
    migrations_root = os.path.join(
        forge_dir, ".ci_support", "migrations", "*.yaml"
    )
    migrations = glob.glob(migrations_root)

    from .variant_algebra import parse_variant, variant_add

    migration_variants = [
        (fn, parse_variant(open(fn, "r").read(), config=config))
        for fn in migrations
    ]
    migration_variants.sort(
        key=lambda fn_v: (fn_v[1]["migration_ts"], fn_v[0])
    )
    if len(migration_variants):
        logger.info(
            f"Applying migrations: {','.join(k for k, v in migration_variants)}"
        )

    for migrator_file, migration in migration_variants:
        if "migration_ts" in migration:
            del migration["migration_ts"]
        if len(migration):
            combined_spec = variant_add(combined_spec, migration)
    return combined_spec


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
):
    if keep_noarchs is None:
        keep_noarchs = [False] * len(platforms)

    metas_list_of_lists = []
    enable_platform = [False] * len(platforms)
    for i, (platform, arch, keep_noarch) in enumerate(
        zip(platforms, archs, keep_noarchs)
    ):
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
            os.path.join(forge_dir, "recipe"), config=config
        )

        migrated_combined_variant_spec = migrate_combined_spec(
            combined_variant_spec, forge_dir, config
        )

        metas = conda_build.api.render(
            os.path.join(forge_dir, "recipe"),
            platform=platform,
            arch=arch,
            ignore_system_variants=True,
            variants=migrated_combined_variant_spec,
            permit_undefined_jinja=True,
            finalize=False,
            bypass_env_check=True,
            channel_urls=forge_config.get("channels", {}).get("sources", []),
        )

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
            "linux": "Linux",
            "osx": "OSX",
            "win": "Windows",
            "linux_aarch64": "aarch64",
            "linux_armv7l": "armv7l",
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

                plat_arch = (
                    platform
                    if arch == "64"
                    else "{}_{}".format(platform, arch)
                )
                forge_config[plat_arch]["enabled"] = True

                fancy_platforms.append(fancy_name[platform])
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

        forge_config["configs"] = configs

        forge_config["fast_finish"] = _get_fast_finish_script(
            provider_name,
            forge_dir=forge_dir,
            forge_config=forge_config,
            fast_finish_text=fast_finish_text,
        )

        # If the recipe supplies its own upload_or_check_non_existence.py upload script,
        # we use it instead of the global one.
        upload_fpath = os.path.join(
            forge_dir, "recipe", "upload_or_check_non_existence.py"
        )
        if os.path.exists(upload_fpath):
            if provider_name == "circle":
                forge_config[
                    "upload_script"
                ] = "/home/conda/recipe_root/upload_or_check_non_existence.py"
            elif provider_name == "travis":
                forge_config[
                    "upload_script"
                ] = "{}/upload_or_check_non_existence.py".format(
                    forge_config["recipe_dir"]
                )
            else:
                forge_config[
                    "upload_script"
                ] = "{}\\upload_or_check_non_existence.py".format(
                    forge_config["recipe_dir"]
                )
        else:
            forge_config["upload_script"] = "upload_or_check_non_existence"

        # hook for extending with whatever platform specific junk we need.
        #     Function passed in as argument
        for platform, enable in zip(platforms, enable_platform):
            if enable:
                platform_specific_setup(
                    jinja_env=jinja_env,
                    forge_dir=forge_dir,
                    forge_config=deepcopy(forge_config),
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
    return forge_config


def _get_build_setup_line(forge_dir, platform, forge_config):
    # If the recipe supplies its own run_conda_forge_build_setup script_linux,
    # we use it instead of the global one.
    if platform == "linux":
        cfbs_fpath = os.path.join(
            forge_dir, "recipe", "run_conda_forge_build_setup_linux"
        )
    elif platform == "win":
        cfbs_fpath = os.path.join(
            forge_dir, "recipe", "run_conda_forge_build_setup_win.bat"
        )
    else:
        cfbs_fpath = os.path.join(
            forge_dir, "recipe", "run_conda_forge_build_setup_osx"
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
                # Overriding global run_conda_forge_build_setup_win with local copy.
                {recipe_dir}\\run_conda_forge_build_setup_win
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
                run_conda_forge_build_setup

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
        yum_build_setup = generate_yum_requirements(forge_dir)
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
        template_files.append(".circleci/run_osx_build.sh")

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


def generate_yum_requirements(forge_dir):
    # If there is a "yum_requirements.txt" file in the recipe, we honour it.
    yum_requirements_fpath = os.path.join(
        forge_dir, "recipe", "yum_requirements.txt"
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
    for platform in ["linux", "osx", "win"]:
        for arch in ["64", "aarch64", "ppc64le", "armv7l"]:
            platform_arch = (
                platform if arch == "64" else "{}_{}".format(platform, arch)
            )
            if platform_arch not in forge_config["provider"]:
                continue
            if forge_config["provider"][platform_arch] == provider:
                platforms.append(platform)
                archs.append(arch)
                if platform == "linux" and arch == "64":
                    keep_noarchs.append(True)
                else:
                    keep_noarchs.append(False)
                upload_packages.append(True)
            elif (
                provider == "azure"
                and forge_config["azure"]["force"]
                and arch == "64"
            ):
                platforms.append(platform)
                archs.append(arch)
                if platform == "linux" and arch == "64":
                    keep_noarchs.append(True)
                else:
                    keep_noarchs.append(False)
                upload_packages.append(False)
    return platforms, archs, keep_noarchs, upload_packages


def render_circle(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, ".circleci", "config.yml")
    template_filename = "circle.yml.tmpl"
    fast_finish_text = textwrap.dedent(
        """\
            {get_fast_finish_script} | \\
                 python - -v --ci "circle" "${{CIRCLE_PROJECT_USERNAME}}/${{CIRCLE_PROJECT_REPONAME}}" "${{CIRCLE_BUILD_NUM}}" "${{CIRCLE_PR_NUMBER}}"
        """
    )  # NOQA
    extra_platform_files = {
        "common": [
            os.path.join(forge_dir, ".circleci", "checkout_merge_commit.sh"),
            os.path.join(forge_dir, ".circleci", "fast_finish_ci_pr_build.sh"),
        ],
        "linux": [
            os.path.join(forge_dir, ".scripts", "run_docker_build.sh"),
            os.path.join(forge_dir, ".scripts", "build_steps.sh"),
        ],
        "osx": [os.path.join(forge_dir, ".circleci", "run_osx_build.sh")],
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
    )


def _travis_specific_setup(jinja_env, forge_config, forge_dir, platform):
    build_setup = _get_build_setup_line(forge_dir, platform, forge_config)

    platform_templates = {
        "linux": [".scripts/run_docker_build.sh", ".scripts/build_steps.sh"],
        "osx": [".travis/run_osx_build.sh"],
        "win": [],
    }
    template_files = platform_templates.get(platform, [])

    if platform == "linux":
        yum_build_setup = generate_yum_requirements(forge_dir)
        if yum_build_setup:
            forge_config["yum_build_setup"] = yum_build_setup

    if platform == "osx":
        build_setup = build_setup.strip()
        build_setup = build_setup.replace("\n", "\n      ")
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
            with open(target_fname, "r") as fh:
                old_file_contents = fh.read()
                if old_file_contents != new_file_contents:
                    raise RuntimeError(
                        "Same file {} is rendered twice with different contents".format(
                            target_fname
                        )
                    )
        with write_file(target_fname) as fh:
            fh.write(new_file_contents)
        # Fix permission of template shell files
        set_exe_file(target_fname, True)


def render_travis(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, ".travis.yml")
    template_filename = "travis.yml.tmpl"
    fast_finish_text = textwrap.dedent(
        """\
        ({get_fast_finish_script} | \\
                  python - -v --ci "travis" "${{TRAVIS_REPO_SLUG}}" "${{TRAVIS_BUILD_NUMBER}}" "${{TRAVIS_PULL_REQUEST}}") || exit 1
    """
    )

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("travis", forge_config)

    extra_platform_files = {
        "linux": [
            os.path.join(forge_dir, ".scripts", "run_docker_build.sh"),
            os.path.join(forge_dir, ".scripts", "build_steps.sh"),
        ],
        "osx": [os.path.join(forge_dir, ".scripts", "run_osx_build.sh")],
    }

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
        extra_platform_files=extra_platform_files,
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


def render_appveyor(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, ".appveyor.yml")
    fast_finish_text = textwrap.dedent(
        """\
            {get_fast_finish_script}
            "%CONDA_INSTALL_LOCN%\\python.exe" {fast_finish_script}.py -v --ci "appveyor" "%APPVEYOR_ACCOUNT_NAME%/%APPVEYOR_PROJECT_SLUG%" "%APPVEYOR_BUILD_NUMBER%" "%APPVEYOR_PULL_REQUEST_NUMBER%"
        """
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
    )


def _azure_specific_setup(jinja_env, forge_config, forge_dir, platform):

    build_setup = _get_build_setup_line(forge_dir, platform, forge_config)

    if platform == "linux":
        yum_build_setup = generate_yum_requirements(forge_dir)
        if yum_build_setup:
            forge_config["yum_build_setup"] = yum_build_setup

    forge_config["build_setup"] = build_setup

    platform_templates = {
        "linux": [
            ".scripts/run_docker_build.sh",
            ".scripts/build_steps.sh",
            ".azure-pipelines/azure-pipelines-linux.yml",
        ],
        "osx": [".azure-pipelines/azure-pipelines-osx.yml"],
        "win": [".azure-pipelines/azure-pipelines-win.yml"],
    }
    template_files = platform_templates.get(platform, [])

    _render_template_exe_files(
        forge_config=forge_config,
        jinja_env=jinja_env,
        template_files=template_files,
        forge_dir=forge_dir,
    )


def render_azure(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, "azure-pipelines.yml")
    template_filename = "azure-pipelines.yml.tmpl"
    fast_finish_text = ""

    (
        platforms,
        archs,
        keep_noarchs,
        upload_packages,
    ) = _get_platforms_of_provider("azure", forge_config)

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
        yum_build_setup = generate_yum_requirements(forge_dir)
        if yum_build_setup:
            forge_config["yum_build_setup"] = yum_build_setup

    forge_config["build_setup"] = build_setup

    _render_template_exe_files(
        forge_config=forge_config,
        jinja_env=jinja_env,
        template_files=template_files,
        forge_dir=forge_dir,
    )


def render_drone(jinja_env, forge_config, forge_dir):
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
    )


def render_README(jinja_env, forge_config, forge_dir):
    if "README.md" in forge_config["skip_render"]:
        logger.info("README.md rendering is skipped")
        return
    # we only care about the first metadata object for sake of readme
    metas = conda_build.api.render(
        os.path.join(forge_dir, "recipe"),
        exclusive_config_file=forge_config["exclusive_config_file"],
        permit_undefined_jinja=True,
        finalize=False,
        bypass_env_check=True,
        trim_skip=False,
    )

    if "parent_recipe" in metas[0][0].meta["extra"]:
        package_name = metas[0][0].meta["extra"]["parent_recipe"]["name"]
    else:
        package_name = metas[0][0].name()

    ci_support_path = os.path.join(forge_dir, ".ci_support")
    variants = []
    if os.path.exists(ci_support_path):
        for filename in os.listdir(ci_support_path):
            if filename.endswith(".yaml"):
                variant_name, _ = os.path.splitext(filename)
                variants.append(variant_name)

    template = jinja_env.get_template("README.md.tmpl")
    target_fname = os.path.join(forge_dir, "README.md")
    forge_config["noarch_python"] = all(meta[0].noarch for meta in metas)
    forge_config["package"] = metas[0][0]
    forge_config["package_name"] = package_name
    forge_config["variants"] = sorted(variants)
    forge_config["outputs"] = sorted(
        list(OrderedDict((meta[0].name(), None) for meta in metas))
    )
    forge_config["maintainers"] = sorted(
        set(
            chain.from_iterable(
                meta[0].meta["extra"].get("recipe-maintainers", [])
                for meta in metas
            )
        )
    )

    if forge_config["azure"].get("build_id") is None:
        # Try to retrieve the build_id from the interwebs
        try:
            import requests

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
        except (IndexError, IOError):
            pass

    logger.debug("README")
    logger.debug(yaml.dump(forge_config))

    with write_file(target_fname) as fh:
        fh.write(template.render(**forge_config))

    code_owners_file = os.path.join(forge_dir, ".github", "CODEOWNERS")
    if len(forge_config["maintainers"]) > 0:
        with write_file(code_owners_file) as fh:
            line = "*"
            for maintainer in forge_config["maintainers"]:
                line = line + " @" + maintainer
            fh.write(line)
    else:
        remove_file_or_dir(code_owners_file)


def copy_feedstock_content(forge_config, forge_dir):
    feedstock_content = os.path.join(conda_forge_content, "feedstock_content")
    skip_files = ["README", "__pycache__"]
    for f in forge_config["skip_render"]:
        skip_files.append(f)
        logger.info("%s rendering is skipped" % f)
    copytree(feedstock_content, forge_dir, skip_files)


def _load_forge_config(forge_dir, exclusive_config_file):
    config = {
        "docker": {
            "executable": "docker",
            "fallback_image": "condaforge/linux-anvil-comp7",
            "command": "bash",
        },
        "templates": {},
        "drone": {},
        "travis": {},
        "circle": {},
        "appveyor": {},
        "azure": {
            # disallow publication of azure artifacts for now.
            "upload_packages": False,
            # Force building all supported providers.
            "force": True,
            # name and id of azure project that the build pipeline is in
            "project_name": "feedstock-builds",
            "project_id": "84710dde-1620-425b-80d0-4cf5baca359d",
            # Default to a timeout of 6 hours.  This is the maximum for azure by default
            "timeout_minutes": 360,
        },
        "provider": {
            "linux": "azure",
            "osx": "azure",
            "win": "azure",
            # Following platforms are disabled by default
            "linux_aarch64": None,
            "linux_ppc64le": None,
            "linux_armv7l": None,
        },
        "win": {"enabled": False},
        "osx": {"enabled": False},
        "linux": {"enabled": False},
        "linux_aarch64": {"enabled": False},
        "linux_ppc64le": {"enabled": False},
        "linux_armv7l": {"enabled": False},
        # Configurable idle timeout.  Used for packages that don't have chatty enough builds
        # Applicable only to circleci and travis
        "idle_timeout_minutes": None,
        # Compiler stack environment variable
        "compiler_stack": "comp7",
        # Stack variables,  These can be used to impose global defaults for how far we build out
        "min_py_ver": "27",
        "max_py_ver": "37",
        "min_r_ver": "34",
        "max_r_ver": "34",
        "channels": {
            "sources": ["conda-forge", "defaults"],
            "targets": [["conda-forge", "main"]],
        },
        "github": {
            "user_or_org": "conda-forge",
            "repo_name": "",
            "branch_name": "master",
        },
        "recipe_dir": "recipe",
        "skip_render": [],
    }

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
    ]

    for old_file in old_files:
        remove_file_or_dir(os.path.join(forge_dir, old_file))

    forge_yml = os.path.join(forge_dir, "conda-forge.yml")
    if not os.path.exists(forge_yml):
        warnings.warn("No conda-forge.yml found. Assuming default options.")
    else:
        with open(forge_yml, "r") as fh:
            file_config = list(yaml.safe_load_all(fh))[0] or {}

        # check for conda-smithy 2.x matrix which we can't auto-migrate
        # to conda_build_config
        if file_config.get("matrix") and not os.path.exists(
            os.path.join(forge_dir, "recipe", "conda_build_config.yaml")
        ):
            raise ValueError(
                "Cannot rerender with matrix in conda-forge.yml."
                " Please migrate matrix to conda_build_config.yaml and try again."
                " See https://github.com/conda-forge/conda-smithy/wiki/Release-Notes-3.0.0.rc1"
                " for more info."
            )

        if file_config.get("docker") and file_config.get("docker").get(
            "image"
        ):
            raise ValueError(
                "Setting docker image in conda-forge.yml is removed now."
                " Use conda_build_config.yaml instead"
            )

        # The config is just the union of the defaults, and the overriden
        # values.
        for key, value in file_config.items():
            # Deal with dicts within dicts.
            if isinstance(value, dict):
                config_item = config.setdefault(key, value)
                config_item.update(value)
            else:
                config[key] = value

    # Set some more azure defaults
    config["azure"].setdefault("user_or_org", config["github"]["user_or_org"])

    log = yaml.safe_dump(config)
    logger.debug("## CONFIGURATION USED\n")
    logger.debug(log)
    logger.debug("## END CONFIGURATION\n")

    if config["provider"]["linux_aarch64"] in {"default", "native"}:
        config["provider"]["linux_aarch64"] = "drone"

    if config["provider"]["linux_ppc64le"] in {"default", "native"}:
        config["provider"]["linux_ppc64le"] = "travis"

    # Fallback handling set to azure, for platforms that are not fully specified by this time
    for platform in config["provider"]:
        if config["provider"][platform] in {"default", "emulated"}:
            config["provider"][platform] = "azure"
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


def check_version_uptodate(resolve, name, installed_version, error_on_warn):
    from conda_build.conda_interface import VersionOrder, MatchSpec

    available_versions = [
        pkg.version for pkg in resolve.get_pkgs(MatchSpec(name))
    ]
    available_versions = sorted(available_versions, key=VersionOrder)
    most_recent_version = available_versions[-1]
    if installed_version is None:
        msg = "{} is not installed in conda-smithy's environment.".format(name)
    elif VersionOrder(installed_version) < VersionOrder(most_recent_version):
        msg = "{} version ({}) is out-of-date ({}) in conda-smithy's environment.".format(
            name, installed_version, most_recent_version
        )
    else:
        return
    if error_on_warn:
        raise RuntimeError("{} Exiting.".format(msg))
    else:
        logger.info(msg)


def commit_changes(forge_file_directory, commit, cs_ver, cfp_ver, cb_ver):
    if cfp_ver:
        msg = "Re-rendered with conda-build {}, conda-smithy {}, and conda-forge-pinning {}".format(
            cb_ver, cs_ver, cfp_ver
        )
    else:
        msg = "Re-rendered with conda-build {} and conda-smithy {}".format(
            cb_ver, cs_ver
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
                git_args = ["git", "commit", "-m", "MNT: {}".format(msg)]
                if commit == "edit":
                    git_args += ["--edit", "--status", "--verbose"]
                subprocess.check_call(git_args, cwd=forge_file_directory)
                logger.info("")
            else:
                logger.info(
                    "You can commit the changes with:\n\n"
                    '    git commit -m "MNT: {}"\n'.format(msg)
                )
            logger.info("These changes need to be pushed to github!\n")
        else:
            logger.info("No changes made. This feedstock is up-to-date.\n")


def get_cfp_file_path(resolve=None, error_on_warn=True):
    if resolve is None:
        index = conda_build.conda_interface.get_index(
            channel_urls=["conda-forge"]
        )
        resolve = conda_build.conda_interface.Resolve(index)

    installed_vers = conda_build.conda_interface.get_installed_version(
        conda_build.conda_interface.root_dir, ["conda-forge-pinning"]
    )
    cf_pinning_ver = installed_vers["conda-forge-pinning"]
    if cf_pinning_ver:
        check_version_uptodate(
            resolve, "conda-forge-pinning", cf_pinning_ver, error_on_warn
        )
    else:
        raise RuntimeError(
            "Install conda-forge-pinning or edit conda-forge.yml"
        )
    cf_pinning_file = os.path.join(
        conda_build.conda_interface.root_dir, "conda_build_config.yaml"
    )
    if not os.path.exists(cf_pinning_file):
        raise RuntimeError(
            "conda_build_config.yaml from conda-forge-pinning is missing"
        )
    return cf_pinning_file, cf_pinning_ver


def clear_variants(forge_dir):
    "Remove all variant files placed in the .ci_support path"
    if os.path.isdir(os.path.join(forge_dir, ".ci_support")):
        configs = glob.glob(os.path.join(forge_dir, ".ci_support", "*.yaml"))
        for config in configs:
            remove_file(config)


def get_common_scripts(forge_dir):
    for old_file in ["run_docker_build.sh", "build_steps.sh"]:
        yield os.path.join(forge_dir, ".scripts", old_file)


def clear_scripts(forge_dir):
    for folder in [".azure-pipelines", ".circleci", ".drone", ".travis"]:
        for old_file in ["run_docker_build.sh", "build_steps.sh"]:
            remove_file(os.path.join(forge_dir, folder, old_file))


def main(
    forge_file_directory,
    no_check_uptodate=False,
    commit=False,
    exclusive_config_file=None,
    check=False,
):
    import logging

    loglevel = os.environ.get("CONDA_SMITHY_LOGLEVEL", "INFO").upper()
    logger.setLevel(loglevel)

    if check:
        index = conda_build.conda_interface.get_index(
            channel_urls=["conda-forge"]
        )
        r = conda_build.conda_interface.Resolve(index)

        # Check that conda-smithy is up-to-date
        check_version_uptodate(r, "conda-smithy", __version__, True)
        get_cfp_file_path(r, True)
        return True

    error_on_warn = False if no_check_uptodate else True
    index = conda_build.conda_interface.get_index(channel_urls=["conda-forge"])
    r = conda_build.conda_interface.Resolve(index)

    # Check that conda-smithy is up-to-date
    check_version_uptodate(r, "conda-smithy", __version__, error_on_warn)

    forge_dir = os.path.abspath(forge_file_directory)

    if exclusive_config_file is not None:
        exclusive_config_file = os.path.join(forge_dir, exclusive_config_file)
        if not os.path.exists(exclusive_config_file):
            raise RuntimeError("Given exclusive-config-file not found.")
        cf_pinning_ver = None
    else:
        exclusive_config_file, cf_pinning_ver = get_cfp_file_path(
            r, error_on_warn
        )

    config = _load_forge_config(forge_dir, exclusive_config_file)

    for each_ci in ["travis", "circle", "appveyor", "drone"]:
        if config[each_ci].pop("enabled", None):
            warnings.warn(
                "It is not allowed to set the `enabled` parameter for `%s`."
                " All CIs are enabled by default. To disable a CI, please"
                " add `skip: true` to the `build` section of `meta.yaml`"
                " and an appropriate selector so as to disable the build."
                % each_ci
            )

    tmplt_dir = os.path.join(conda_forge_content, "templates")
    # Load templates from the feedstock in preference to the smithy's templates.
    env = Environment(
        extensions=["jinja2.ext.do"],
        loader=FileSystemLoader(
            [os.path.join(forge_dir, "templates"), tmplt_dir]
        ),
    )

    copy_feedstock_content(config, forge_dir)
    if os.path.exists(os.path.join(forge_dir, "build-locally.py")):
        set_exe_file(os.path.join(forge_dir, "build-locally.py"))
    clear_variants(forge_dir)
    clear_scripts(forge_dir)

    render_circle(env, config, forge_dir)
    render_travis(env, config, forge_dir)
    render_appveyor(env, config, forge_dir)
    render_azure(env, config, forge_dir)
    render_drone(env, config, forge_dir)
    render_README(env, config, forge_dir)

    if os.path.isdir(os.path.join(forge_dir, ".ci_support")):
        with write_file(os.path.join(forge_dir, ".ci_support", "README")) as f:
            f.write(
                "This file is automatically generated by conda-smithy.  To change "
                "any matrix elements, you should change conda-smithy's input "
                "conda_build_config.yaml and re-render the recipe, rather than editing "
                "these files directly."
            )

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
        description=("Configure a feedstock given " "a conda-forge.yml file.")
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
