from __future__ import print_function, unicode_literals

import glob
from itertools import product
import os
import textwrap
import yaml
import warnings

import conda_build.api
import conda_build.utils
import conda_build.variants
from jinja2 import Environment, FileSystemLoader

from conda_smithy.feedstock_io import (
    set_exe_file,
    write_file,
    remove_file,
    copy_file,
)

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
                    zipped_configs.append([{k: [squished_variants[k][idx]] for k in group}
                                           for idx, _ in enumerate(squished_variants[key])])
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
    for key, value in squished_variants.items():
        if type(value) in (list, set, tuple):
            squished_variants[key] = sorted(list(value))

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


def _trim_unused_zip_keys(all_used_vars):
    """Remove unused keys in zip_keys sets, so that they don't cause unnecessary missing value
    errors"""
    groups = all_used_vars.get('zip_keys', [])
    if groups and not isinstance(groups[0], list):
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
            if key in all_used_vars:
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

    for meta in list_of_metas:
        all_used_vars.update(meta.get_used_vars())

    top_level_loop_vars = list_of_metas[0].get_used_loop_vars(force_top_level=True)
    top_level_vars = list_of_metas[0].get_used_vars(force_top_level=True)
    if 'target_platform' in all_used_vars:
        top_level_loop_vars.add('target_platform')

    # this is the initial collection of all variants before we discard any.  "Squishing"
    #     them is necessary because the input form is already broken out into one matrix
    #     configuration per item, and we want a single dict, with each key representing many values
    squished_input_variants = conda_build.variants.list_of_dicts_to_dict_of_lists(
        list_of_metas[0].config.input_variants)

    # Add in some variables that should always be preserved
    all_used_vars.update(set(('zip_keys', 'pin_run_as_build', 'MACOSX_DEPLOYMENT_TARGET')))
    all_used_vars.update(top_level_vars)

    all_used_vars = {key: squished_input_variants[key]
                     for key in all_used_vars if key in squished_input_variants}

    _trim_unused_zip_keys(all_used_vars)
    _trim_unused_pin_run_as_build(all_used_vars)

    # to deduplicate potentially zipped keys, we blow out the collection of variables, then
    #     do a set operation, then collapse it again

    all_used_vars = conda_build.variants.dict_of_lists_to_list_of_dicts(
        all_used_vars, extend_keys={'zip_keys', 'pin_run_as_build',
                                    'ignore_version', 'ignore_build_only_deps'})
    all_used_vars = set(conda_build.utils.HashableDict(variant) for variant in all_used_vars)
    all_used_vars = conda_build.variants.list_of_dicts_to_dict_of_lists(list(all_used_vars))

    _trim_unused_zip_keys(all_used_vars)
    _trim_unused_pin_run_as_build(all_used_vars)

    return break_up_top_level_values(top_level_loop_vars, all_used_vars), top_level_loop_vars


def dump_subspace_config_files(metas, root_path, output_name):
    """With conda-build 3, it handles the build matrix.  We take what it spits out, and write a
    config.yaml file for each matrix entry that it spits out.  References to a specific file
    replace all of the old environment variables that specified a matrix entry."""

    # identify how to break up the complete set of used variables.  Anything considered
    #     "top-level" should be broken up into a separate CI job.

    configs, top_level_loop_vars = _collapse_subpackage_variants(metas)

    # get rid of the special object notation in the yaml file for objects that we dump
    yaml.add_representer(set, yaml.representer.SafeRepresenter.represent_list)
    yaml.add_representer(tuple, yaml.representer.SafeRepresenter.represent_list)

    config_names = []
    for config in configs:
        config_name = '{}_{}'.format(output_name, package_key(config, top_level_loop_vars,
                                                              metas[0].config.subdir))
        out_folder = os.path.join(root_path, '.ci_support')
        out_path = os.path.join(out_folder, config_name) + '.yaml'
        if not os.path.isdir(out_folder):
            os.makedirs(out_folder)

        with write_file(out_path) as f:
            yaml.dump(config, f, default_flow_style=False)
        config_names.append(config_name)
    return sorted(config_names)


def _get_fast_finish_script(provider_name, forge_config, forge_dir, fast_finish_text):
    get_fast_finish_script = ""
    fast_finish_script = ""
    cfbs_fpath = os.path.join(forge_dir, 'recipe', 'ff_ci_pr_build.py')
    if provider_name == 'appveyor':
        if os.path.exists(cfbs_fpath):
            fast_finish_script = "{recipe_dir}\\ff_ci_pr_build".format(
                recipe_dir=forge_config["recipe_dir"])
        else:
            get_fast_finish_script = '''powershell -Command "(New-Object Net.WebClient).DownloadFile('https://raw.githubusercontent.com/conda-forge/conda-forge-build-setup-feedstock/master/recipe/ff_ci_pr_build.py', 'ff_ci_pr_build.py')"'''  # NOQA
            fast_finish_script += "ff_ci_pr_build"
            fast_finish_text += "del {fast_finish_script}.py"

        fast_finish_text = fast_finish_text.format(
            get_fast_finish_script=get_fast_finish_script,
            fast_finish_script=fast_finish_script,
        )

        fast_finish_text = fast_finish_text.strip()
        fast_finish_text = fast_finish_text.replace("\n", "\n        ")
    else:
        # If the recipe supplies its own conda-forge-build-setup script,
        # we use it instead of the global one.
        if os.path.exists(cfbs_fpath):
            get_fast_finish_script += "cat {recipe_dir}/ff_ci_pr_build.py".format(
                recipe_dir=forge_config["recipe_dir"])
        else:
            get_fast_finish_script += "curl https://raw.githubusercontent.com/conda-forge/conda-forge-build-setup-feedstock/master/recipe/ff_ci_pr_build.py"  # NOQA

        fast_finish_text = fast_finish_text.format(
            get_fast_finish_script=get_fast_finish_script
        )

        fast_finish_text = fast_finish_text.strip()
    return fast_finish_text


def _render_ci_provider(provider_name, jinja_env, forge_config, forge_dir, platform, arch,
                        fast_finish_text, platform_target_path, platform_template_file,
                        platform_specific_setup, keep_noarch=False, extra_platform_files=None):
    metas = conda_build.api.render(os.path.join(forge_dir, 'recipe'),
                                   variant_config_files=forge_config['variant_config_files'],
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

    if os.path.isdir(os.path.join(forge_dir, '.ci_support')):
        configs = glob.glob(os.path.join(forge_dir, '.ci_support',
                                         '{}_*'.format(provider_name)))
        for config in configs:
            remove_file(config)

    if not metas or all(m.skip() for m in metas):
        # There are no cases to build (not even a case without any special
        # dependencies), so remove the run_docker_build.sh if it exists.
        forge_config[provider_name]["enabled"] = False

        extra_platform_files = [] if not extra_platform_files else extra_platform_files
        target_fnames = [platform_target_path] + extra_platform_files
        for each_target_fname in target_fnames:
            remove_file(each_target_fname)
    else:
        forge_config[provider_name]["enabled"] = True

        forge_config['configs'] = dump_subspace_config_files(metas, forge_dir, provider_name)

        forge_config['fast_finish'] = _get_fast_finish_script(provider_name,
                                                              forge_dir=forge_dir,
                                                              forge_config=forge_config,
                                                              fast_finish_text=fast_finish_text)

        # If the recipe supplies its own conda-forge-build-setup upload script,
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
        platform_specific_setup(jinja_env=jinja_env, forge_dir=forge_dir, forge_config=forge_config)

        template = jinja_env.get_template(platform_template_file)
        with write_file(platform_target_path) as fh:
            fh.write(template.render(**forge_config))

    # circleci needs a placeholder file of sorts - always write the output, even if no metas
    if provider_name == 'circle':
        template = jinja_env.get_template(platform_template_file)
        with write_file(platform_target_path) as fh:
            fh.write(template.render(**forge_config))
    return forge_config


def _circle_specific_setup(jinja_env, forge_config, forge_dir):
    # If the recipe supplies its own conda-forge-build-setup script,
    # we use it instead of the global one.
    cfbs_fpath = os.path.join(forge_dir, 'recipe', 'run_conda_forge_build_setup_linux')

    build_setup = ""
    if os.path.exists(cfbs_fpath):
        build_setup += textwrap.dedent("""\
            # Overriding global conda-forge-build-setup with local copy.
            source /home/conda/recipe_root/run_conda_forge_build_setup_linux

        """)
    else:
        build_setup += textwrap.dedent("""\
            source run_conda_forge_build_setup

        """)

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
            # run "conda smithy rerender" and this line be updated
            # automatically.
            /usr/bin/sudo -n yum install -y {}


        """.format(' '.join(requirements)))

    forge_config['build_setup'] = build_setup

    # TODO: Conda has a convenience for accessing nested yaml content.
    template = jinja_env.get_template('run_docker_build.tmpl')
    target_fname = os.path.join(forge_dir, '.circleci', 'run_docker_build.sh')
    with write_file(target_fname) as fh:
        fh.write(template.render(**forge_config))

    template_name = 'fast_finish_ci_pr_build.sh.tmpl'
    template = jinja_env.get_template(template_name)
    target_fname = os.path.join(forge_dir, '.circleci', 'fast_finish_ci_pr_build.sh')
    with write_file(target_fname) as fh:
        fh.write(template.render(**forge_config))

    # Fix permissions.
    target_fnames = [
        os.path.join(forge_dir, '.circleci', 'checkout_merge_commit.sh'),
        os.path.join(forge_dir, '.circleci', 'fast_finish_ci_pr_build.sh'),
        os.path.join(forge_dir, '.circleci', 'run_docker_build.sh'),
    ]
    for each_target_fname in target_fnames:
        set_exe_file(each_target_fname, True)


def render_circle(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, '.circleci', 'config.yml')
    template_filename = 'circle.yml.tmpl'
    fast_finish_text = textwrap.dedent("""\
            {get_fast_finish_script} | \\
                 python - -v --ci "circle" "${{CIRCLE_PROJECT_USERNAME}}/${{CIRCLE_PROJECT_REPONAME}}" "${{CIRCLE_BUILD_NUM}}" "${{CIRCLE_PR_NUMBER}}"
        """)  # NOQA
    extra_platform_files = [
        os.path.join(forge_dir, '.circleci', 'checkout_merge_commit.sh'),
        os.path.join(forge_dir, '.circleci', 'fast_finish_ci_pr_build.sh'),
        os.path.join(forge_dir, '.circleci', 'run_docker_build.sh'),
        ]

    return _render_ci_provider('circle', jinja_env=jinja_env, forge_config=forge_config,
                               forge_dir=forge_dir, platform='linux', arch='64',
                               fast_finish_text=fast_finish_text, platform_target_path=target_path,
                               platform_template_file=template_filename,
                               platform_specific_setup=_circle_specific_setup, keep_noarch=True,
                               extra_platform_files=extra_platform_files)


def _travis_specific_setup(jinja_env, forge_config, forge_dir):
    build_setup = ""
    # If the recipe supplies its own conda-forge-build-setup script,
    # we use it instead of the global one.
    cfbs_fpath = os.path.join(forge_dir, 'recipe', 'run_conda_forge_build_setup_osx')
    if os.path.exists(cfbs_fpath):
        build_setup += textwrap.dedent("""\
            # Overriding global conda-forge-build-setup with local copy.
            source {recipe_dir}/run_conda_forge_build_setup_osx
        """.format(recipe_dir=forge_config["recipe_dir"]))
    else:
        build_setup += textwrap.dedent("""\
            source run_conda_forge_build_setup
        """)

    build_setup = build_setup.strip()
    build_setup = build_setup.replace("\n", "\n      ")
    forge_config['build_setup'] = build_setup


def render_travis(jinja_env, forge_config, forge_dir):
    target_path = os.path.join(forge_dir, '.travis.yml')
    template_filename = 'travis.yml.tmpl'
    fast_finish_text = textwrap.dedent("""\
        ({get_fast_finish_script} | \\
                  python - -v --ci "travis" "${{TRAVIS_REPO_SLUG}}" "${{TRAVIS_BUILD_NUMBER}}" "${{TRAVIS_PULL_REQUEST}}") || exit 1
    """)

    return _render_ci_provider('travis', jinja_env=jinja_env, forge_config=forge_config,
                               forge_dir=forge_dir, platform='osx', arch='64',
                               fast_finish_text=fast_finish_text, platform_target_path=target_path,
                               platform_template_file=template_filename,
                               platform_specific_setup=_travis_specific_setup)


def _appveyor_specific_setup(jinja_env, forge_config, forge_dir):
    build_setup = ""
    # If the recipe supplies its own conda-forge-build-setup script,
    # we use it instead of the global one.
    cfbs_fpath = os.path.join(forge_dir, 'recipe', 'run_conda_forge_build_setup_win.bat')
    if os.path.exists(cfbs_fpath):
        build_setup += textwrap.dedent("""\
            # Overriding global conda-forge-build-setup with local copy.
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

    return _render_ci_provider('appveyor', jinja_env=jinja_env, forge_config=forge_config,
                               forge_dir=forge_dir, platform='win', arch='64',
                               fast_finish_text=fast_finish_text, platform_target_path=target_path,
                               platform_template_file=template_filename,
                               platform_specific_setup=_appveyor_specific_setup)


def render_README(jinja_env, forge_config, forge_dir):
    # we only care about the first metadata object for sake of readme
    meta = conda_build.api.render(os.path.join(forge_dir, 'recipe'),
                                  variant_config_files=forge_config['variant_config_files'],
                                  permit_undefined_jinja=True, finalize=False,
                                  bypass_env_check=True)[0][0]
    template = jinja_env.get_template('README.md.tmpl')
    target_fname = os.path.join(forge_dir, 'README.md')
    forge_config['noarch_python'] = meta.noarch
    forge_config['package'] = meta
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


def _load_forge_config(forge_dir, variant_config_files):
    config = {'docker': {'executable': 'docker',
                         'image': 'condaforge/linux-anvil',
                         'command': 'bash'},
              'templates': {},
              'travis': {},
              'circle': {},
              'appveyor': {},
              'variant_config_files': variant_config_files,
              'channels': {'sources': ['conda-forge', 'defaults'],
                           'targets': [['conda-forge', 'main']]},
              'github': {'user_or_org': 'conda-forge', 'repo_name': ''},
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
    ]
    for old_file in old_files:
        remove_file(os.path.join(forge_dir, old_file))

    forge_yml = os.path.join(forge_dir, "conda-forge.yml")
    if not os.path.exists(forge_yml):
        warnings.warn('No conda-forge.yml found. Assuming default options.')
    else:
        with open(forge_yml, "r") as fh:
            file_config = list(yaml.load_all(fh))[0] or {}
        # The config is just the union of the defaults, and the overriden
        # values.
        for key, value in file_config.items():
            config_item = config.setdefault(key, value)
            # Deal with dicts within dicts.
            if isinstance(value, dict):
                config_item.update(value)
    config['package'] = os.path.basename(forge_dir)
    if not config['github']['repo_name']:
        feedstock_name = os.path.basename(forge_dir)
        if not feedstock_name.endswith("-feedstock"):
            feedstock_name += "-feedstock"
        config['github']['repo_name'] = feedstock_name
    return config


def main(forge_file_directory, variant_config_files):
    forge_dir = os.path.abspath(forge_file_directory)
    config = _load_forge_config(forge_dir, variant_config_files)

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
    render_README(env, config, forge_dir)

    if os.path.isdir(os.path.join(forge_dir, '.ci_support')):
        with write_file(os.path.join(forge_dir, '.ci_support', 'README')) as f:
            f.write("This file is automatically generated by conda-smithy.  To change "
                    "any matrix elements, you should change conda-smithy's input "
                    "conda_build_config.yaml and re-render the recipe, rather than editing "
                    "these files directly.")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=('Configure a feedstock given '
                                                  'a conda-forge.yml file.'))
    parser.add_argument('forge_file_directory',
                        help=('the directory containing the conda-forge.yml file '
                              'used to configure the feedstock'))

    args = parser.parse_args()
    main(args.forge_file_directory)
