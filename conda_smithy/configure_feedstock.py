from __future__ import print_function, unicode_literals

from contextlib import contextmanager
import os
import re
import shutil
import textwrap
import yaml
import warnings

try:
    # Try conda's API in newer 4.2.x and 4.3.x.
    from conda.exports import (
        DEFAULT_CHANNELS_UNIX,
        DEFAULT_CHANNELS_WIN,
    )
except ImportError:
    try:
        # Fallback for old versions of 4.2.x and 4.3.x.
        from conda.base.constants import (
            DEFAULT_CHANNELS_UNIX,
            DEFAULT_CHANNELS_WIN,
        )
    except ImportError:
        # Fallback for very old conda (e.g. 4.1.x).
        DEFAULT_CHANNELS_UNIX = (
            'https://repo.continuum.io/pkgs/free',
            'https://repo.continuum.io/pkgs/pro',
        )

        DEFAULT_CHANNELS_WIN = (
            'https://repo.continuum.io/pkgs/free',
            'https://repo.continuum.io/pkgs/pro',
            'https://repo.continuum.io/pkgs/msys2',
        )

import conda_build.api
from conda_build.metadata import MetaData
from jinja2 import Environment, FileSystemLoader

from conda_smithy.feedstock_io import (
    set_exe_file,
    write_file,
    remove_file,
    copy_file,
)

conda_forge_content = os.path.abspath(os.path.dirname(__file__))


def meta_config(meta):
    if hasattr(meta, 'config'):
        config = meta.config
    else:
        config = conda_build.config
    return config


def package_key(meta):
    # get the build string from whatever conda-build makes of the configuration
    variables = meta.get_loop_vars()
    used_variables = set()
    requirements = meta.extract_requirements_text().rstrip()
    if not requirements:
        requirements = (meta.get_value('requirements/build') +
                        meta.get_value('requirements/run') +
                        meta.get_value('requirements/host'))
        requirements = '- ' + "\n- ".join(requirements)
    for v in variables:
        variant_regex = r"(\s*\{\{\s*%s\s*(?:.*?)?\}\})" % v
        requirement_regex = r"(\-\s+%s(?:\s+|$))" % v
        all_res = '|'.join((variant_regex, requirement_regex))
        compiler_match = re.match(r'(.*?)_compiler$', v)
        if compiler_match:
            compiler_regex = (
                r"(\s*\{\{\s*compiler\([\'\"]%s[\"\'].*\)\s*\}\})" % compiler_match.group(1))
            all_res = '|'.join((all_res, compiler_regex))
        if re.search(all_res, requirements, flags=re.MULTILINE | re.DOTALL):
            used_variables.add(v)
    build_vars = ''.join([k + str(meta.config.variant[k]) for k in sorted(list(used_variables))])
    # kind of a special case.  Target platform determines a lot of output behavior, but may not be
    #    explicitly listed in the recipe.
    tp = meta.config.variant.get('target_platform')
    if tp and tp != meta.config.subdir and 'target_platform' not in build_vars:
        build_vars += 'target-' + tp
    key = []
    if build_vars:
        key.append(build_vars)
    key = "-".join(key)
    return key


def copytree(src, dst, ignore=(), root_dst=None):
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


def rmtree(src):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        if os.path.isdir(s):
            rmtree(s)
        else:
            remove_file(s)


def dump_subspace_config_folder(meta, root_path, output_dir):
    if meta.meta_path:
        recipe = os.path.dirname(meta.meta_path)
    else:
        recipe = meta.get('extra', {}).get('parent_recipe', {})
    assert recipe, ("no parent recipe set, and no path associated with this metadata")
    # make recipe path relative
    recipe = recipe.replace(root_path + '/', '')
    folder_name = package_key(meta)
    # copy base recipe into a folder named for this node
    out_folder = os.path.join(output_dir, folder_name)
    if os.path.isdir(out_folder):
        rmtree(out_folder)
    os.makedirs(out_folder)
    # write the conda_build_config.yml for this particular metadata into that
    #   recipe This should sit alongside meta.yaml, where conda-build will be
    #   able to find it
    # get rid of the special object notation in the yaml file for objects that we dump
    yaml.add_representer(set, yaml.representer.SafeRepresenter.represent_list)
    yaml.add_representer(tuple, yaml.representer.SafeRepresenter.represent_list)

    # sort keys so that we don't have random shuffling in config values showing up in diffs
    for k, v in meta.config.squished_variants.items():
        if type(v) in [list, set, tuple]:
            meta.config.squished_variants[k] = sorted(list(v))

    with write_file(os.path.join(out_folder, 'conda_build_config.yaml')) as f:
        yaml.dump(meta.config.squished_variants, f, default_flow_style=False)
    return folder_name


def render_circle(jinja_env, forge_config, forge_dir):
    metas = conda_build.api.render(os.path.join(forge_dir, 'recipe'),
                                   variant_config_files=forge_config['variant_config_files'],
                                   platform='linux', arch='64',
                                   permit_undefined_jinja=True, finalize=False,
                                   bypass_env_check=True)

    build_configurations = os.path.join(forge_dir, 'circle')
    if os.path.isdir(build_configurations):
        # this takes care of removing any existing git-registered files
        rmtree(build_configurations)
    if os.path.isdir(build_configurations):
        # this takes care of removing any files not registered with git
        shutil.rmtree(build_configurations)

    if not metas:
        # There are no cases to build (not even a case without any special
        # dependencies), so remove the run_docker_build.sh if it exists.
        forge_config["circle"]["enabled"] = False

        target_fnames = [
            os.path.join(forge_dir, 'ci_support', 'checkout_merge_commit.sh'),
            os.path.join(forge_dir, 'ci_support', 'fast_finish_ci_pr_build.sh'),
            os.path.join(forge_dir, 'ci_support', 'run_docker_build.sh'),
        ]
        for each_target_fname in target_fnames:
            remove_file(each_target_fname)
    else:
        forge_config["circle"]["enabled"] = True

        os.makedirs(build_configurations)
        folders = []
        for meta, _, _ in metas:
            folders.append(dump_subspace_config_folder(meta, forge_dir, build_configurations))
        forge_config['folders'] = folders

        fast_finish = textwrap.dedent("""\
            {get_fast_finish_script} | \\
                 python - -v --ci "circle" "${{CIRCLE_PROJECT_USERNAME}}/${{CIRCLE_PROJECT_REPONAME}}" "${{CIRCLE_BUILD_NUM}}" "${{CIRCLE_PR_NUMBER}}"
        """)
        get_fast_finish_script = ""

        # If the recipe supplies its own conda-forge-build-setup script,
        # we use it instead of the global one.
        cfbs_fpath = os.path.join(forge_dir, 'recipe',
                                  'ff_ci_pr_build.py')
        if os.path.exists(cfbs_fpath):
            get_fast_finish_script += "cat {recipe_dir}/ff_ci_pr_build.py".format(recipe_dir=forge_config["recipe_dir"])
        else:
            get_fast_finish_script += "curl https://raw.githubusercontent.com/conda-forge/conda-forge-build-setup-feedstock/master/recipe/ff_ci_pr_build.py"

        fast_finish = fast_finish.format(
            get_fast_finish_script=get_fast_finish_script
        )

        fast_finish = fast_finish.strip()

        forge_config['fast_finish'] = fast_finish

        build_setup = ""

        # If the recipe supplies its own conda-forge-build-setup script,
        # we use it instead of the global one.
        cfbs_fpath = os.path.join(forge_dir, 'recipe',
                                  'run_conda_forge_build_setup_linux')
        if os.path.exists(cfbs_fpath):
            build_setup += textwrap.dedent("""\
                # Overriding global conda-forge-build-setup with local copy.
                source /recipe_root/run_conda_forge_build_setup_linux

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

        # If the recipe supplies its own conda-forge-build-setup upload script,
        # we use it instead of the global one.
        upload_fpath = os.path.join(forge_dir, 'recipe',
                                    'upload_or_check_non_existence.py')
        if os.path.exists(upload_fpath):
            forge_config['upload_script'] = (
                "/recipe_root/upload_or_check_non_existence.py"
            )
        else:
            forge_config['upload_script'] = "upload_or_check_non_existence"

        # TODO: Conda has a convenience for accessing nested yaml content.
        template_name = 'run_docker_build.tmpl'
        template = jinja_env.get_template(template_name)
        target_fname = os.path.join(forge_dir, 'ci_support', 'run_docker_build.sh')
        with write_file(target_fname) as fh:
            fh.write(template.render(**forge_config))

        template_name = 'fast_finish_ci_pr_build.sh.tmpl'
        template = jinja_env.get_template(template_name)
        target_fname = os.path.join(forge_dir, 'ci_support', 'fast_finish_ci_pr_build.sh')
        with write_file(target_fname) as fh:
            fh.write(template.render(**forge_config))

        # Fix permissions.
        target_fnames = [
            os.path.join(forge_dir, 'ci_support', 'checkout_merge_commit.sh'),
            os.path.join(forge_dir, 'ci_support', 'fast_finish_ci_pr_build.sh'),
            os.path.join(forge_dir, 'ci_support', 'run_docker_build.sh'),
        ]
        for each_target_fname in target_fnames:
            set_exe_file(each_target_fname, True)

    target_fname = os.path.join(forge_dir, '.circleci', 'config.yml')
    template = jinja_env.get_template('circle.yml.tmpl')
    with write_file(target_fname) as fh:
        fh.write(template.render(**forge_config))


def render_travis(jinja_env, forge_config, forge_dir):
    metas = conda_build.api.render(os.path.join(forge_dir, 'recipe'),
                                   variant_config_files=forge_config['variant_config_files'],
                                   platform='osx', arch='64',
                                   permit_undefined_jinja=True, finalize=False,
                                   bypass_env_check=True)

    to_delete = []
    for idx, (meta, _, _) in enumerate(metas):
        if meta.noarch:
            # do not build noarch, including noarch: python, packages on Travis CI.
            to_delete.append(idx)
    for idx in to_delete:
        del metas[idx]

    target_fname = os.path.join(forge_dir, '.travis.yml')

    build_configurations = os.path.join(forge_dir, 'travis')
    if os.path.isdir(build_configurations):
        # this takes care of removing any existing git-registered files
        rmtree(build_configurations)
    if os.path.isdir(build_configurations):
        # this takes care of removing any files not registered with git
        shutil.rmtree(build_configurations)

    if not metas:
        # There are no cases to build (not even a case without any special
        # dependencies), so remove the .travis.yml if it exists.
        forge_config["travis"]["enabled"] = False
        remove_file(target_fname)
    else:
        os.makedirs(build_configurations)
        folders = []
        for meta, _, _ in metas:
            folders.append(dump_subspace_config_folder(meta, forge_dir, build_configurations))

        forge_config["travis"]["enabled"] = True
        fast_finish = textwrap.dedent("""\
            ({get_fast_finish_script} | \\
                python - -v --ci "travis" "${{TRAVIS_REPO_SLUG}}" "${{TRAVIS_BUILD_NUMBER}}" "${{TRAVIS_PULL_REQUEST}}") || exit 1
        """)
        get_fast_finish_script = ""

        # If the recipe supplies its own conda-forge-build-setup script,
        # we use it instead of the global one.
        cfbs_fpath = os.path.join(forge_dir, 'recipe',
                                  'ff_ci_pr_build.py')
        if os.path.exists(cfbs_fpath):
            get_fast_finish_script += "cat {recipe_dir}/ff_ci_pr_build.py".format(recipe_dir=forge_config["recipe_dir"])
        else:
            get_fast_finish_script += "curl https://raw.githubusercontent.com/conda-forge/conda-forge-build-setup-feedstock/master/recipe/ff_ci_pr_build.py"

        fast_finish = fast_finish.format(
            get_fast_finish_script=get_fast_finish_script
        )

        fast_finish = fast_finish.strip()
        fast_finish = fast_finish.replace("\n", "\n      ")

        forge_config['fast_finish'] = fast_finish

        build_setup = ""

        # If the recipe supplies its own conda-forge-build-setup script,
        # we use it instead of the global one.
        cfbs_fpath = os.path.join(forge_dir, 'recipe',
                                  'run_conda_forge_build_setup_osx')
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
        forge_config['folders'] = folders

        # If the recipe supplies its own conda-forge-build-setup upload script,
        # we use it instead of the global one.
        upload_fpath = os.path.join(forge_dir, 'recipe',
                                    'upload_or_check_non_existence.py')
        if os.path.exists(upload_fpath):
            forge_config['upload_script'] = (
                "{recipe_dir}/upload_or_check_non_existence.py".format(
                    recipe_dir=forge_config["recipe_dir"]
                )
            )
        else:
            forge_config['upload_script'] = "upload_or_check_non_existence"

        template = jinja_env.get_template('travis.yml.tmpl')
        with write_file(target_fname) as fh:
            fh.write(template.render(**forge_config))


def render_README(jinja_env, forge_config, forge_dir):
    # we only care about the first metadata object for sake of readme
    meta = conda_build.api.render(os.path.join(forge_dir, 'recipe'),
                                  permit_undefined_jinja=True, finalize=False,
                                  bypass_env_check=True)[0][0]
    template = jinja_env.get_template('README.md.tmpl')
    target_fname = os.path.join(forge_dir, 'README.md')
    if meta.noarch:
        forge_config['noarch_python'] = True
    else:
        forge_config['noarch_python'] = False
    forge_config['package'] = meta
    with write_file(target_fname) as fh:
        fh.write(template.render(**forge_config))


def render_appveyor(jinja_env, forge_config, forge_dir):
    metas = conda_build.api.render(os.path.join(forge_dir, 'recipe'),
                                   variant_config_files=forge_config['variant_config_files'],
                                   platform='win', arch='64',
                                   permit_undefined_jinja=True, finalize=False,
                                   bypass_env_check=True)

    to_delete = []
    for idx, (meta, _, _) in enumerate(metas):
        if meta.noarch:
            # do not build noarch, including noarch: python, packages on Travis CI.
            to_delete.append(idx)
    for idx in to_delete:
        del metas[idx]

    target_fname = os.path.join(forge_dir, 'appveyor.yml')

    build_configurations = os.path.join(forge_dir, 'appveyor')
    if os.path.isdir(build_configurations):
        # this takes care of removing any existing git-registered files
        rmtree(build_configurations)
    if os.path.isdir(build_configurations):
        # this takes care of removing any files not registered with git
        shutil.rmtree(build_configurations)

    if not metas:
        # There are no cases to build (not even a case without any special
        # dependencies), so remove the appveyor.yml if it exists.
        forge_config["appveyor"]["enabled"] = False
        remove_file(target_fname)
    else:
        forge_config["appveyor"]["enabled"] = True

        os.makedirs(build_configurations)
        folders = []
        for meta, _, _ in metas:
            folders.append(dump_subspace_config_folder(meta, forge_dir, build_configurations))
        forge_config['folders'] = folders

        get_fast_finish_script = ""
        fast_finish_script = ""
        fast_finish = textwrap.dedent("""\
            {get_fast_finish_script}
            {fast_finish_script} -v --ci "appveyor" "%APPVEYOR_ACCOUNT_NAME%/%APPVEYOR_PROJECT_SLUG%" "%APPVEYOR_BUILD_NUMBER%" "%APPVEYOR_PULL_REQUEST_NUMBER%"
        """)

        # If the recipe supplies its own conda-forge-build-setup script,
        # we use it instead of the global one.
        cfbs_fpath = os.path.join(forge_dir, 'recipe',
                                  'ff_ci_pr_build.py')
        if os.path.exists(cfbs_fpath):
            fast_finish_script += "{recipe_dir}\\ff_ci_pr_build".format(recipe_dir=forge_config["recipe_dir"])
        else:
            get_fast_finish_script += '''powershell -Command "(New-Object Net.WebClient).DownloadFile('https://raw.githubusercontent.com/conda-forge/conda-forge-build-setup-feedstock/master/recipe/ff_ci_pr_build.py', 'ff_ci_pr_build.py')"'''
            fast_finish_script += "ff_ci_pr_build"
            fast_finish += "del {fast_finish_script}.py"

        fast_finish = fast_finish.format(
            get_fast_finish_script=get_fast_finish_script,
            fast_finish_script=fast_finish_script,
        )

        fast_finish = fast_finish.strip()
        fast_finish = fast_finish.replace("\n", "\n        ")

        forge_config['fast_finish'] = fast_finish

        build_setup = ""

        # If the recipe supplies its own conda-forge-build-setup script,
        # we use it instead of the global one.
        cfbs_fpath = os.path.join(forge_dir, 'recipe',
                                  'run_conda_forge_build_setup_osx')
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

        # If the recipe supplies its own conda-forge-build-setup upload script,
        # we use it instead of the global one.
        upload_fpath = os.path.join(forge_dir, 'recipe',
                                    'upload_or_check_non_existence.py')
        if os.path.exists(upload_fpath):
            forge_config['upload_script'] = (
                "{recipe_dir}\\upload_or_check_non_existence".format(
                    recipe_dir=forge_config["recipe_dir"]
                )
            )
        else:
            forge_config['upload_script'] = "upload_or_check_non_existence"

        template = jinja_env.get_template('appveyor.yml.tmpl')
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


def meta_of_feedstock(forge_dir, config=None):
    recipe_dir = 'recipe'
    meta_dir = os.path.join(forge_dir, recipe_dir)
    if not os.path.exists(meta_dir):
        raise IOError("The given directory isn't a feedstock.")
    if hasattr(conda_build, 'api'):
        meta = MetaData(meta_dir, config=config)
    else:
        meta = MetaData(meta_dir)
    return meta


def main(forge_file_directory, variant_config_files):
    recipe_dir = 'recipe'
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
              'recipe_dir': recipe_dir}
    forge_dir = os.path.abspath(forge_file_directory)

    # An older conda-smithy used to have some files which should no longer exist,
    # remove those now.
    old_files = [
        'disabled_appveyor.yml',
        os.path.join('ci_support', 'upload_or_check_non_existence.py'),
        'circle.yml',
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
    config['package'] = forge_file_directory
    if not config['github']['repo_name']:
        feedstock_name = os.path.basename(forge_dir)
        if not feedstock_name.endswith("-feedstock"):
            feedstock_name += "-feedstock"
        config['github']['repo_name'] = feedstock_name

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


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=('Configure a feedstock given '
                                                  'a conda-forge.yml file.'))
    parser.add_argument('forge_file_directory',
                        help=('the directory containing the conda-forge.yml file '
                              'used to configure the feedstock'))

    args = parser.parse_args()
    main(args.forge_file_directory)
