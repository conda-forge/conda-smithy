from __future__ import print_function, unicode_literals

import glob
from itertools import product, chain
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
from jinja2 import Environment, FileSystemLoader

from conda_smithy.feedstock_io import (
    set_exe_file,
    write_file,
    remove_file,
    copy_file,
)
from . import __version__

conda_forge_content = os.path.abspath(os.path.dirname(__file__))


def package_key(config, used_loop_vars, subdir):
    # get the build string from whatever conda-build makes of the configuration
    build_vars = ''.join([k + str(config[k][0]) for k in sorted(list(used_loop_vars))])
    key = []
    # kind of a special case.  Target platform determines a lot of output behavior, but may not be
    #    explicitly listed in the recipe.
    tp = config.get('target_platform')
    if tp and isinstance(tp, list):
        tp = tp[0]
    if tp and tp != subdir and 'target_platform' not in build_vars:
        build_vars += 'target-' + tp
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
    if 'zip_keys' in squished_variants:
        zip_key_groups = squished_variants['zip_keys']
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
                                top_level_config.append(squished_variants[k][idx])
                        top_level_config = tuple(top_level_config)
                        if top_level_config not in top_level_config_dict:
                            top_level_config_dict[top_level_config] = []
                        top_level_config_dict[top_level_config].append({k: [squished_variants[k][idx]] for k in group})
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
            top_level_dimensions.append([{key: [val]} for val in squished_variants[key]])
            del squished_variants[key]

    configs = []
    dimensions = []

    # sort values so that the diff doesn't show randomly changing order

    if 'zip_keys' in squished_variants:
        zip_key_groups = squished_variants['zip_keys']

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
    return pkg.replace('-', '_')


def _trim_unused_zip_keys(all_used_vars):
    """Remove unused keys in zip_keys sets, so that they don't cause unnecessary missing value
    errors"""
    groups = all_used_vars.get('zip_keys', [])
    if groups and not any(isinstance(groups[0], obj) for obj in (list, tuple)):
        groups = [groups]
    used_groups = []
    for group in groups:
        used_keys_in_group = [k for k in group if k in all_used_vars]
        if len(used_keys_in_group) > 1:
            used_groups.append(used_keys_in_group)
    if used_groups:
        all_used_vars['zip_keys'] = used_groups
    elif 'zip_keys' in all_used_vars:
        del all_used_vars['zip_keys']


def _trim_unused_pin_run_as_build(all_used_vars):
    """Remove unused keys in pin_run_as_build sets"""
    pkgs = all_used_vars.get('pin_run_as_build', {})
    used_pkgs = {}
    if pkgs:
        for key in pkgs.keys():
            if _package_var_name(key) in all_used_vars:
                used_pkgs[key] = pkgs[key]
    if used_pkgs:
        all_used_vars['pin_run_as_build'] = used_pkgs
    elif 'pin_run_as_build' in all_used_vars:
        del all_used_vars['pin_run_as_build']


def _collapse_subpackage_variants(list_of_metas):
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
        all_variants.update(conda_build.utils.HashableDict(v) for v in meta.config.variants)
        all_variants.add(conda_build.utils.HashableDict(meta.config.variant))

    top_level_loop_vars = list_of_metas[0].get_used_loop_vars(force_top_level=True)
    top_level_vars = list_of_metas[0].get_used_vars(force_top_level=True)
    if 'target_platform' in all_used_vars:
        top_level_loop_vars.add('target_platform')

    # this is the initial collection of all variants before we discard any.  "Squishing"
    #     them is necessary because the input form is already broken out into one matrix
    #     configuration per item, and we want a single dict, with each key representing many values
    squished_input_variants = conda_build.variants.list_of_dicts_to_dict_of_lists(
        list_of_metas[0].config.input_variants)
    squished_used_variants = conda_build.variants.list_of_dicts_to_dict_of_lists(list(all_variants))

    # these are variables that only occur in the top level, and thus won't show up as loops in the
    #     above collection of all variants.  We need to transfer them from the input_variants.
    preserve_top_level_loops = set(top_level_loop_vars) - set(all_used_vars)

    # Add in some variables that should always be preserved
    always_keep_keys = set(('zip_keys', 'pin_run_as_build', 'MACOSX_DEPLOYMENT_TARGET',
                            'macos_min_version', 'macos_machine',
                            'channel_sources', 'channel_targets', 'docker_image', 'build_number_decrement'))
    all_used_vars.update(always_keep_keys)
    all_used_vars.update(top_level_vars)

    used_key_values = {key: squished_input_variants[key]
                       for key in all_used_vars if key in squished_input_variants}

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
        used_key_values, extend_keys={'zip_keys', 'pin_run_as_build',
                                      'ignore_version', 'ignore_build_only_deps'})
    used_key_values = set(conda_build.utils.HashableDict(variant) for variant in used_key_values)
    used_key_values = conda_build.variants.list_of_dicts_to_dict_of_lists(list(used_key_values))

    _trim_unused_zip_keys(used_key_values)
    _trim_unused_pin_run_as_build(used_key_values)

    return break_up_top_level_values(top_level_loop_vars, used_key_values), top_level_loop_vars


def _yaml_represent_ordereddict(yaml_representer, data):
    # represent_dict processes dict-likes with a .sort() method or plain iterables of key-value
    #     pairs. Only for the latter it never sorts and retains the order of the OrderedDict.
    return yaml.representer.SafeRepresenter.represent_dict(yaml_representer, data.items())


def finalize_config(config, platform):
    """Specialized handling to deal with the dual compiler output state.
    In a future state this SHOULD go away"""
    # TODO: REMOVE WHEN NO LONGER NEEDED
    if platform in {'linux', 'osx'}:
        if len({'c_compiler', 'cxx_compiler', 'fortran_compiler'} & set(config.keys())):
            # we have a compiled source here so the zip should take care of things appropriately
            pass
        else:
            try:
                # prefer to build with the newer compiler image, This ensures that for things that don't declare they need
                # compilers, they will fail
                config['docker_image'] = [config['docker_image'][-1]]
            except KeyError:
                config['docker_image'] = ['condaforge/linux-anvil']

            try:
                config['channel_sources'] = [config['channel_sources'][0]]
            except KeyError:
                config['channel_sources'] = ['conda-forge,defaults']

            try:
                config['channel_targets'] = [config['channel_targets'][0]]
            except KeyError:
                config['channel_targets'] = ['conda-forge main']

            try:
                config['build_number_decrement'] = [config['build_number_decrement'][-1]]
            except KeyError:
                config['build_number_decrement'] = ['0']

    return config


def dump_subspace_config_files(metas, root_path, platform):
    """With conda-build 3, it handles the build matrix.  We take what it spits out, and write a
    config.yaml file for each matrix entry that it spits out.  References to a specific file
    replace all of the old environment variables that specified a matrix entry."""

    # identify how to break up the complete set of used variables.  Anything considered
    #     "top-level" should be broken up into a separate CI job.

    configs, top_level_loop_vars = _collapse_subpackage_variants(metas)

    # get rid of the special object notation in the yaml file for objects that we dump
    yaml.add_representer(set, yaml.representer.SafeRepresenter.represent_list)
    yaml.add_representer(tuple, yaml.representer.SafeRepresenter.represent_list)
    yaml.add_representer(OrderedDict, _yaml_represent_ordereddict)

    result = []
    for config in configs:
        config_name = '{}_{}'.format(platform, package_key(config, top_level_loop_vars,
                                                           metas[0].config.subdir))
        out_folder = os.path.join(root_path, '.ci_support')
        out_path = os.path.join(out_folder, config_name) + '.yaml'
        if not os.path.isdir(out_folder):
            os.makedirs(out_folder)

        config = finalize_config(config, platform)
        with write_file(out_path) as f:
            yaml.dump(config, f, default_flow_style=False)
        target_platform = config.get("target_platform", [platform])[0]
        result.append((config_name, target_platform))
    return sorted(result)


def _get_fast_finish_script(provider_name, forge_config, forge_dir, fast_finish_text):
    get_fast_finish_script = ""
    fast_finish_script = ""
    tooling_branch = 'branch2.0'

    cfbs_fpath = os.path.join(forge_dir, 'recipe', 'ff_ci_pr_build.py')
    if provider_name == 'appveyor':
        if os.path.exists(cfbs_fpath):
            fast_finish_script = "{recipe_dir}\\ff_ci_pr_build".format(
                recipe_dir=forge_config["recipe_dir"])
        else:
            get_fast_finish_script = '''powershell -Command "(New-Object Net.WebClient).DownloadFile('https://raw.githubusercontent.com/conda-forge/conda-forge-ci-setup-feedstock/{branch}/recipe/conda_forge_ci_setup/ff_ci_pr_build.py', 'ff_ci_pr_build.py')"'''  # NOQA
            fast_finish_script += "ff_ci_pr_build"
            fast_finish_text += "del {fast_finish_script}.py"

        fast_finish_text = fast_finish_text.format(
            get_fast_finish_script=get_fast_finish_script.format(branch=tooling_branch),
            fast_finish_script=fast_finish_script,
        )

        fast_finish_text = fast_finish_text.strip()
        fast_finish_text = fast_finish_text.replace("\n", "\n        ")
    else:
        # If the recipe supplies its own ff_ci_pr_build.py script,
        # we use it instead of the global one.
        if os.path.exists(cfbs_fpath):
            get_fast_finish_script += "cat {recipe_dir}/ff_ci_pr_build.py".format(
                recipe_dir=forge_config["recipe_dir"])
        else:
            get_fast_finish_script += "curl https://raw.githubusercontent.com/conda-forge/conda-forge-ci-setup-feedstock/{branch}/recipe/conda_forge_ci_setup/ff_ci_pr_build.py"  # NOQA

        fast_finish_text = fast_finish_text.format(
            get_fast_finish_script=get_fast_finish_script.format(branch=tooling_branch)
        )

        fast_finish_text = fast_finish_text.strip()
    return fast_finish_text


def _render_ci_provider(provider_name, jinja_env, forge_config, forge_dir, platforms, archs,
                        fast_finish_text, platform_target_path, platform_template_file,
                        platform_specific_setup, keep_noarchs=None, extra_platform_files={}):

    if keep_noarchs is None:
        keep_noarchs = [False]*len(platforms)

    metas_list_of_lists = []
    enable_platform = [False]*len(platforms)
    for i, (platform, arch, keep_noarch) in enumerate(zip(platforms, archs, keep_noarchs)):
        metas = conda_build.api.render(os.path.join(forge_dir, 'recipe'),
                                   exclusive_config_file=forge_config['exclusive_config_file'],
                                   platform=platform, arch=arch,
                                   permit_undefined_jinja=True, finalize=False,
                                   bypass_env_check=True,
                                   channel_urls=forge_config.get('channels', {}).get('sources', []))
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

    if os.path.isdir(os.path.join(forge_dir, '.ci_support')):
        configs = glob.glob(os.path.join(forge_dir, '.ci_support',
                                         '{}_*'.format(provider_name)))
        for config in configs:
            remove_file(config)

        for platform in platforms:
            configs = glob.glob(os.path.join(forge_dir, '.ci_support',
                                             '{}_*'.format(platform)))
            for config in configs:
                remove_file(config)

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
        fancy_name = {'linux': 'Linux', 'osx': 'OSX', 'win': 'Windows'}
        fancy_platforms = []
        unfancy_platforms = set()

        configs = []
        for metas, platform, enable in zip(metas_list_of_lists, platforms, enable_platform):
            if enable:
                configs.extend(dump_subspace_config_files(metas, forge_dir, platform))
                forge_config[platform]["enabled"] = True
                fancy_platforms.append(fancy_name[platform])
                unfancy_platforms.add(platform)
            elif platform in extra_platform_files:
                    for each_target_fname in extra_platform_files[platform]:
                        remove_file(each_target_fname)

        for key in extra_platform_files.keys():
            if key != 'common' and key not in platforms:
                for each_target_fname in extra_platform_files[key]:
                    remove_file(each_target_fname)

        forge_config[provider_name]["platforms"] = ','.join(fancy_platforms)
        forge_config[provider_name]["all_platforms"] = list(unfancy_platforms)

        forge_config['configs'] = configs

        forge_config['fast_finish'] = _get_fast_finish_script(provider_name,
                                                              forge_dir=forge_dir,
                                                              forge_config=forge_config,
                                                              fast_finish_text=fast_finish_text)

        # Allow disabling publication for a whole provider.  This is useful for testing new providers
        forge_config['upload_packages'] = (forge_config.get(provider_name, {})
                                                       .get('upload_packages', True))

        # If the recipe supplies its own upload_or_check_non_existence.py upload script,
        # we use it instead of the global one.
        upload_fpath = os.path.join(forge_dir, 'recipe',
                                    'upload_or_check_non_existence.py')
        if os.path.exists(upload_fpath):
            if provider_name == "circle":
                forge_config['upload_script'] = (
                    "/home/conda/recipe_root/upload_or_check_non_existence.py"
                )
            elif provider_name == "travis":
                forge_config['upload_script'] = (
                    "{}/upload_or_check_non_existence.py".format(forge_config["recipe_dir"])
                )
            else:
                forge_config['upload_script'] = (
                    "{}\\upload_or_check_non_existence.py".format(forge_config["recipe_dir"])
                )
        else:
            forge_config['upload_script'] = "upload_or_check_non_existence"

        # hook for extending with whatever platform specific junk we need.
        #     Function passed in as argument
        for platform, enable in zip(platforms, enable_platform):
            if enable:
                platform_specific_setup(jinja_env=jinja_env, forge_dir=forge_dir,
                                    forge_config=forge_config, platform=platform)

        template = jinja_env.get_template(platform_template_file)
        with write_file(platform_target_path) as fh:
            fh.write(template.render(**forge_config))

    # circleci needs a placeholder file of sorts - always write the output, even if no metas
    if provider_name == 'circle':
        template = jinja_env.get_template(platform_template_file)
        with write_file(platform_target_path) as fh:
            fh.write(template.render(**forge_config))
    # TODO: azure-pipelines might need the same as circle
    return forge_config


def _circle_specific_setup(jinja_env, forge_config, forge_dir, platform):
    # If the recipe supplies its own run_conda_forge_build_setup script_linux,
    # we use it instead of the global one.
    if platform == 'linux':
        cfbs_fpath = os.path.join(forge_dir, 'recipe', 'run_conda_forge_build_setup_linux')
    else:
        cfbs_fpath = os.path.join(forge_dir, 'recipe', 'run_conda_forge_build_setup_osx')

    build_setup = ""
    if os.path.exists(cfbs_fpath):
        if platform == 'linux':
            build_setup += textwrap.dedent("""\
                # Overriding global run_conda_forge_build_setup_linux with local copy.
                source /home/conda/recipe_root/run_conda_forge_build_setup_linux

            """)
        else:
            build_setup += textwrap.dedent("""\
                # Overriding global run_conda_forge_build_setup_osx with local copy.
                source {recipe_dir}/run_conda_forge_build_setup_osx
            """.format(recipe_dir=forge_config["recipe_dir"]))
    else:
        build_setup += textwrap.dedent("""\
            source run_conda_forge_build_setup

        """)

    if platform == 'linux':
        # If there is a "yum_requirements.txt" file in the recipe, we honour it.
        yum_requirements_fpath = os.path.join(forge_dir, 'recipe',
                                              'yum_requirements.txt')
        if os.path.exists(yum_requirements_fpath):
            with open(yum_requirements_fpath) as fh:
                requirements = [line.strip() for line in fh
                                if line.strip() and not line.strip().startswith('#')]
            if not requirements:
                raise ValueError("No yum requirements enabled in the "
                                 "yum_requirements.txt, please remove the file "
                                 "or add some.")
            build_setup += textwrap.dedent("""\

                # Install the yum requirements defined canonically in the
                # "recipe/yum_requirements.txt" file. After updating that file,
                # run "conda smithy rerender" and this line will be updated
                # automatically.
                /usr/bin/sudo -n yum install -y {}


            """.format(' '.join(requirements)))

    forge_config['build_setup'] = build_setup

    if platform == 'linux':
        run_file_name = 'run_docker_build'
    else:
        run_file_name = 'run_osx_build'

    # TODO: Conda has a convenience for accessing nested yaml content.
    template_files = [
        '{}.sh.tmpl'.format(run_file_name),
        'fast_finish_ci_pr_build.sh.tmpl',
    ]

    if platform == 'linux':
        template_files.append('build_steps.sh.tmpl')

    _render_template_exe_files(forge_config=forge_config,
                               target_dir=os.path.join(forge_dir, '.circleci'),
                               jinja_env=jinja_env,
                               template_files=template_files)

    # Fix permission of other shell files.
    target_fnames = [
        os.path.join(forge_dir, '.circleci', 'checkout_merge_commit.sh'),
    ]
    for target_fname in target_fnames:
        set_exe_file(target_fname, True)


def _get_platforms_of_provider(provider, forge_config):
    platforms = []
    keep_noarchs = []
    # TODO arch seems meaningless now for most of smithy? REMOVE?
    archs = []
    for platform in ['linux', 'osx', 'win']:
        if forge_config['provider'][platform] == provider:
            platforms.append(platform)
            if platform == 'linux':
                keep_noarchs.append(True)
            else:
                keep_noarchs.append(False)
            archs.append('64')
    return platforms, archs, keep_noarchs


def render_circle(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, '.circleci', 'config.yml')
    template_filename = 'circle.yml.tmpl'
    fast_finish_text = textwrap.dedent("""\
            {get_fast_finish_script} | \\
                 python - -v --ci "circle" "${{CIRCLE_PROJECT_USERNAME}}/${{CIRCLE_PROJECT_REPONAME}}" "${{CIRCLE_BUILD_NUM}}" "${{CIRCLE_PR_NUMBER}}"
        """)  # NOQA
    extra_platform_files = {
        'common': [
            os.path.join(forge_dir, '.circleci', 'checkout_merge_commit.sh'),
            os.path.join(forge_dir, '.circleci', 'fast_finish_ci_pr_build.sh'),
        ],
        'linux': [
            os.path.join(forge_dir, '.circleci', 'run_docker_build.sh'),
            os.path.join(forge_dir, '.circleci', 'build_steps.sh'),
        ],
        'osx': [
            os.path.join(forge_dir, '.circleci', 'run_osx_build.sh'),
        ]
    }

    platforms, archs, keep_noarchs = _get_platforms_of_provider('circle', forge_config)

    return _render_ci_provider('circle', jinja_env=jinja_env, forge_config=forge_config,
                               forge_dir=forge_dir, platforms=platforms, archs=archs,
                               fast_finish_text=fast_finish_text, platform_target_path=target_path,
                               platform_template_file=template_filename,
                               platform_specific_setup=_circle_specific_setup, keep_noarchs=keep_noarchs,
                               extra_platform_files=extra_platform_files)


def _travis_specific_setup(jinja_env, forge_config, forge_dir, platform):
    build_setup = ""
    # If the recipe supplies its own run_conda_forge_build_setup script_osx,
    # we use it instead of the global one.
    cfbs_fpath = os.path.join(forge_dir, 'recipe', 'run_conda_forge_build_setup_osx')
    if os.path.exists(cfbs_fpath):
        build_setup += textwrap.dedent("""\
            # Overriding global run_conda_forge_build_setup_osx with local copy.
            source {recipe_dir}/run_conda_forge_build_setup_osx
        """.format(recipe_dir=forge_config["recipe_dir"]))
    else:
        build_setup += textwrap.dedent("""\
            source run_conda_forge_build_setup
        """)

    # TODO: Conda has a convenience for accessing nested yaml content.
    template_files = [
    ]

    _render_template_exe_files(forge_config=forge_config,
                               target_dir=os.path.join(forge_dir, '.travis'),
                               jinja_env=jinja_env,
                               template_files=template_files)

    build_setup = build_setup.strip()
    build_setup = build_setup.replace("\n", "\n      ")
    forge_config['build_setup'] = build_setup


def _render_template_exe_files(forge_config, target_dir, jinja_env, template_files):
    for template_file in template_files:
        template = jinja_env.get_template(template_file)
        target_fname = os.path.join(target_dir, template_file[:-len('.tmpl')])
        with write_file(target_fname) as fh:
            fh.write(template.render(**forge_config))
        # Fix permission of template shell files
        set_exe_file(target_fname, True)


def render_travis(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, '.travis.yml')
    template_filename = 'travis.yml.tmpl'
    fast_finish_text = textwrap.dedent("""\
        ({get_fast_finish_script} | \\
                  python - -v --ci "travis" "${{TRAVIS_REPO_SLUG}}" "${{TRAVIS_BUILD_NUMBER}}" "${{TRAVIS_PULL_REQUEST}}") || exit 1
    """)

    platforms, archs, keep_noarchs = _get_platforms_of_provider('travis', forge_config)

    return _render_ci_provider('travis', jinja_env=jinja_env, forge_config=forge_config,
                               forge_dir=forge_dir, platforms=platforms, archs=archs,
                               fast_finish_text=fast_finish_text, platform_target_path=target_path,
                               platform_template_file=template_filename, keep_noarchs=keep_noarchs,
                               platform_specific_setup=_travis_specific_setup,
                               )


def _appveyor_specific_setup(jinja_env, forge_config, forge_dir, platform):
    build_setup = ""
    # If the recipe supplies its own run_conda_forge_build_setup_win.bat script,
    # we use it instead of the global one.
    cfbs_fpath = os.path.join(forge_dir, 'recipe', 'run_conda_forge_build_setup_win.bat')
    if os.path.exists(cfbs_fpath):
        build_setup += textwrap.dedent("""\
            # Overriding global run_conda_forge_build_setup_win with local copy.
            {recipe_dir}\\run_conda_forge_build_setup_win
        """.format(recipe_dir=forge_config["recipe_dir"]))
    else:
        build_setup += textwrap.dedent("""\

            run_conda_forge_build_setup
        """)

    build_setup = build_setup.rstrip()
    build_setup = build_setup.replace("\n", "\n    - cmd: ")
    build_setup = build_setup.lstrip()

    forge_config['build_setup'] = build_setup


def render_appveyor(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, '.appveyor.yml')
    fast_finish_text = textwrap.dedent("""\
            {get_fast_finish_script}
            {fast_finish_script} -v --ci "appveyor" "%APPVEYOR_ACCOUNT_NAME%/%APPVEYOR_PROJECT_SLUG%" "%APPVEYOR_BUILD_NUMBER%" "%APPVEYOR_PULL_REQUEST_NUMBER%"
        """)
    template_filename = 'appveyor.yml.tmpl'

    platforms, archs, keep_noarchs = _get_platforms_of_provider('appveyor', forge_config)

    return _render_ci_provider('appveyor', jinja_env=jinja_env, forge_config=forge_config,
                               forge_dir=forge_dir, platforms=platforms, archs=archs,
                               fast_finish_text=fast_finish_text, platform_target_path=target_path,
                               platform_template_file=template_filename, keep_noarchs=keep_noarchs,
                               platform_specific_setup=_appveyor_specific_setup)


def _azure_specific_setup(jinja_env, forge_config, forge_dir, platform):
    # TODO:
    platform_templates = {
        'linux': [
            'azure-pipelines-linux.yml.tmpl',
            'run_docker_build.sh.tmpl',
            'build_steps.sh.tmpl',
        ],
        'osx': [
            'azure-pipelines-osx.yml.tmpl',
        ],
        'win': [
            'azure-pipelines-win.yml.tmpl',
        ],
    }
    template_files = platform_templates.get(platform, [])

    forge_config['docker']['interactive'] = False
    _render_template_exe_files(forge_config=forge_config,
                               target_dir=os.path.join(forge_dir, '.azure-pipelines'),
                               jinja_env=jinja_env,
                               template_files=template_files)
    forge_config['docker']['interactive'] = True


def _get_azure_platforms(provider, forge_config):
    platforms = []
    keep_noarchs = []
    # TODO arch seems meaningless now for most of smithy? REMOVE?
    archs = []
    for platform in ['linux', 'osx', 'win']:
        if forge_config['azure']['force'] or (forge_config['provider'][platform] == provider):
            platforms.append(platform)
            if platform == 'linux':
                keep_noarchs.append(True)
            else:
                keep_noarchs.append(False)
            archs.append('64')
    return platforms, archs, keep_noarchs


def render_azure(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, 'azure-pipelines.yml')
    template_filename = 'azure-pipelines.yml.tmpl'
    fast_finish_text = ""

    # TODO: for now just get this ignoring other pieces
    platforms, archs, keep_noarchs = _get_azure_platforms('azure', forge_config)

    return _render_ci_provider('azure',
                               jinja_env=jinja_env,
                               forge_config=forge_config,
                               forge_dir=forge_dir,
                               platforms=platforms,
                               archs=archs,
                               fast_finish_text=fast_finish_text,
                               platform_target_path=target_path,
                               platform_template_file=template_filename,
                               platform_specific_setup=_azure_specific_setup,
                               keep_noarchs=keep_noarchs,)


def render_README(jinja_env, forge_config, forge_dir):
    # we only care about the first metadata object for sake of readme
    metas = conda_build.api.render(os.path.join(forge_dir, 'recipe'),
                                  exclusive_config_file=forge_config['exclusive_config_file'],
                                  permit_undefined_jinja=True, finalize=False,
                                  bypass_env_check=True, trim_skip=False)

    if "parent_recipe" in metas[0][0].meta["extra"]:
        package_name = metas[0][0].meta["extra"]["parent_recipe"]["name"]
    else:
        package_name = metas[0][0].meta.name()

    template = jinja_env.get_template('README.md.tmpl')
    target_fname = os.path.join(forge_dir, 'README.md')
    forge_config['noarch_python'] = all(meta[0].noarch for meta in metas)
    forge_config['package'] = metas[0][0]
    forge_config['package_name'] = package_name
    forge_config['outputs'] = sorted(list(OrderedDict((meta[0].name(), None) for meta in metas)))
    forge_config['maintainers'] = sorted(set(chain.from_iterable(meta[0].meta['extra'].get('recipe-maintainers', []) for meta in metas)))
    with write_file(target_fname) as fh:
        fh.write(template.render(**forge_config))


def copy_feedstock_content(forge_dir):
    feedstock_content = os.path.join(conda_forge_content,
                                     'feedstock_content')
    copytree(
        feedstock_content,
        forge_dir,
        'README'
    )


def _load_forge_config(forge_dir, exclusive_config_file):
    config = {'docker': {'executable': 'docker',
                         'image': 'condaforge/linux-anvil',
                         'command': 'bash',
                         'interactive': True,
                         },
              'templates': {},
              'travis': {},
              'circle': {},
              'appveyor': {},
              'azure': {
                  # disallow publication of azure artifacts for now.
                  'upload_packages': False,
                  # Force building all supported providers.
                  'force': True,

              },
              'provider': {'linux': 'circle', 'osx': 'travis', 'win': 'appveyor'},
              'win': {'enabled': False},
              'osx': {'enabled': False},
              'linux': {'enabled': False},
              # Compiler stack environment variable
              'compiler_stack': 'comp4',
              # Stack variables,  These can be used to impose global defaults for how far we build out
              'min_py_ver': '27',
              'max_py_ver': '36',
              'min_r_ver': '34',
              'max_r_ver': '34',

              'channels': {'sources': ['conda-forge', 'defaults'],
                           'targets': [['conda-forge', 'main']]},
              'github': {'user_or_org': 'conda-forge',
                         'repo_name': '',
                         'branch_name': 'master'},
              'recipe_dir': 'recipe'}

    # An older conda-smithy used to have some files which should no longer exist,
    # remove those now.
    old_files = [
        'disabled_appveyor.yml',
        os.path.join('ci_support', 'upload_or_check_non_existence.py'),
        'circle.yml',
        'appveyor.yml',
        os.path.join('ci_support', 'checkout_merge_commit.sh'),
        os.path.join('ci_support', 'fast_finish_ci_pr_build.sh'),
        os.path.join('ci_support', 'run_docker_build.sh'),
        'LICENSE',
    ]
    for old_file in old_files:
        remove_file(os.path.join(forge_dir, old_file))

    forge_yml = os.path.join(forge_dir, "conda-forge.yml")
    if not os.path.exists(forge_yml):
        warnings.warn('No conda-forge.yml found. Assuming default options.')
    else:
        with open(forge_yml, "r") as fh:
            file_config = list(yaml.load_all(fh))[0] or {}

        # check for conda-smithy 2.x matrix which we can't auto-migrate
        # to conda_build_config
        if file_config.get('matrix') and not os.path.exists(
            os.path.join(forge_dir, 'recipe', 'conda_build_config.yaml')
        ):
            # FIXME: update docs URL
            raise ValueError(
                'Cannot rerender with matrix in conda-forge.yml.'
                ' Please migrate matrix to conda_build_config.yaml and try again.'
                ' See https://github.com/conda-forge/conda-smithy/wiki/Release-Notes-3.0.0.rc1'
                ' for more info.')

        # The config is just the union of the defaults, and the overriden
        # values.
        for key, value in file_config.items():
            # Deal with dicts within dicts.
            if isinstance(value, dict):
                config_item = config.setdefault(key, value)
                config_item.update(value)
            else:
                config[key] = value

    # Set the environment variable for the compiler stack
    os.environ['CF_COMPILER_STACK'] = config['compiler_stack']
    # Set valid ranger for the supported platforms
    os.environ['CF_MIN_PY_VER'] = config['min_py_ver']
    os.environ['CF_MAX_PY_VER'] = config['max_py_ver']
    os.environ['CF_MIN_R_VER'] = config['min_r_ver']
    os.environ['CF_MAX_R_VER'] = config['max_r_ver']

    config['package'] = os.path.basename(forge_dir)
    if not config['github']['repo_name']:
        feedstock_name = os.path.basename(forge_dir)
        if not feedstock_name.endswith("-feedstock"):
            feedstock_name += "-feedstock"
        config['github']['repo_name'] = feedstock_name
    config['exclusive_config_file'] = exclusive_config_file
    return config


def check_version_uptodate(resolve, name, installed_version, error_on_warn):
    from conda_build.conda_interface import VersionOrder, MatchSpec
    available_versions = [pkg.version for pkg in resolve.get_pkgs(MatchSpec(name))]
    available_versions = sorted(available_versions, key=VersionOrder)
    most_recent_version = available_versions[-1]
    if installed_version is None:
        msg = "{} is not installed in root env.".format(name)
    elif VersionOrder(installed_version) < VersionOrder(most_recent_version):
        msg = "{} version in root env ({}) is out-of-date ({}).".format(
            name, installed_version, most_recent_version)
    else:
        return
    if error_on_warn:
        raise RuntimeError("{} Exiting.".format(msg))
    else:
        print(msg)


def commit_changes(forge_file_directory, commit, cs_ver, cfp_ver):
    if cfp_ver:
        msg = 'Re-rendered with conda-smithy {} and pinning {}'.format(cs_ver, cfp_ver)
    else:
        msg = 'Re-rendered with conda-smithy {}'.format(cs_ver)
    print(msg)

    is_git_repo = os.path.exists(os.path.join(forge_file_directory, ".git"))
    if is_git_repo:
        has_staged_changes = subprocess.call(
            [
                "git", "diff", "--cached", "--quiet", "--exit-code"
            ],
            cwd=forge_file_directory
        )
        if has_staged_changes:
            if commit:
                git_args = [
                    'git',
                    'commit',
                    '-m',
                    'MNT: {}'.format(msg)
                ]
                if commit == "edit":
                    git_args += [
                        '--edit',
                        '--status',
                        '--verbose'
                    ]
                subprocess.check_call(
                    git_args,
                    cwd=forge_file_directory
                )
                print("")
            else:
                print(
                    'You can commit the changes with:\n\n'
                    '    git commit -m "MNT: {}"\n'.format(msg)
                )
            print("These changes need to be pushed to github!\n")
        else:
            print("No changes made. This feedstock is up-to-date.\n")


def get_cfp_file_path(resolve=None, error_on_warn=True):
    if resolve is None:
        index = conda_build.conda_interface.get_index(channel_urls=['conda-forge'])
        resolve = conda_build.conda_interface.Resolve(index)

    installed_vers = conda_build.conda_interface.get_installed_version(
                            conda_build.conda_interface.root_dir, ["conda-forge-pinning"])
    cf_pinning_ver = installed_vers["conda-forge-pinning"]
    if cf_pinning_ver:
        check_version_uptodate(resolve, "conda-forge-pinning", cf_pinning_ver, error_on_warn)
    else:
        raise RuntimeError("Install conda-forge-pinning or edit conda-forge.yml")
    cf_pinning_file = os.path.join(conda_build.conda_interface.root_dir, "conda_build_config.yaml")
    if not os.path.exists(cf_pinning_file):
        raise RuntimeError("conda_build_config.yaml from conda-forge-pinning is missing")
    return cf_pinning_file, cf_pinning_ver


def main(forge_file_directory, no_check_uptodate, commit, exclusive_config_file):
    error_on_warn = False if no_check_uptodate else True
    index = conda_build.conda_interface.get_index(channel_urls=['conda-forge'])
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
        exclusive_config_file, cf_pinning_ver = get_cfp_file_path(r, error_on_warn)

    config = _load_forge_config(forge_dir, exclusive_config_file)

    for each_ci in ["travis", "circle", "appveyor"]:
        if config[each_ci].pop("enabled", None):
            warnings.warn(
                "It is not allowed to set the `enabled` parameter for `%s`."
                " All CIs are enabled by default. To disable a CI, please"
                " add `skip: true` to the `build` section of `meta.yaml`"
                " and an appropriate selector so as to disable the build." \
                % each_ci
            )

    tmplt_dir = os.path.join(conda_forge_content, 'templates')
    # Load templates from the feedstock in preference to the smithy's templates.
    env = Environment(extensions=['jinja2.ext.do'],
                      loader=FileSystemLoader([os.path.join(forge_dir, 'templates'),
                                               tmplt_dir]))

    copy_feedstock_content(forge_dir)

    render_circle(env, config, forge_dir)
    render_travis(env, config, forge_dir)
    render_appveyor(env, config, forge_dir)
    render_azure(env, config, forge_dir)
    render_README(env, config, forge_dir)

    if os.path.isdir(os.path.join(forge_dir, '.ci_support')):
        with write_file(os.path.join(forge_dir, '.ci_support', 'README')) as f:
            f.write("This file is automatically generated by conda-smithy.  To change "
                    "any matrix elements, you should change conda-smithy's input "
                    "conda_build_config.yaml and re-render the recipe, rather than editing "
                    "these files directly.")

    commit_changes(forge_file_directory, commit, __version__, cf_pinning_ver)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=('Configure a feedstock given '
                                                  'a conda-forge.yml file.'))
    parser.add_argument('forge_file_directory',
                        help=('the directory containing the conda-forge.yml file '
                              'used to configure the feedstock'))

    args = parser.parse_args()
    main(args.forge_file_directory)
