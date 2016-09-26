from __future__ import print_function

from contextlib import contextmanager
import os
import shutil
import stat
import textwrap
import yaml
import warnings

import conda.api
import conda.config
import conda_build.metadata
try:
    import conda_build.api
except ImportError:
    # old conda-build
    pass
from conda_build.metadata import MetaData
from conda_build_all.version_matrix import special_case_version_matrix, filter_cases
from conda_build_all.resolved_distribution import ResolvedDistribution
from jinja2 import Environment, FileSystemLoader

conda_forge_content = os.path.abspath(os.path.dirname(__file__))


def meta_config(meta):
    if hasattr(meta, 'config'):
        config = meta.config
    else:
        config = conda_build.config
    return config


def render_run_docker_build(jinja_env, forge_config, forge_dir):
    meta = forge_config['package']
    with fudge_subdir('linux-64', build_config=meta_config(meta)):
        meta.parse_again()
        matrix = compute_build_matrix(meta, forge_config.get('matrix'))
        cases_not_skipped = []
        for case in matrix:
            pkgs, vars = split_case(case)
            with enable_vars(vars):
                if not ResolvedDistribution(meta, pkgs).skip():
                    cases_not_skipped.append(vars + sorted(pkgs))
        matrix = sorted(cases_not_skipped, key=sort_without_target_arch)

    target_fname = os.path.join(forge_dir, 'ci_support', 'run_docker_build.sh')
    if not matrix:
        # There are no cases to build (not even a case without any special
        # dependencies), so remove the run_docker_build.sh if it exists.
        forge_config["circle"]["enabled"] = False
        if os.path.exists(target_fname):
            os.remove(target_fname)
    else:
        forge_config["circle"]["enabled"] = True
        matrix = prepare_matrix_for_env_vars(matrix)
        forge_config = update_matrix(forge_config, matrix)

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
            build_setup = textwrap.dedent("""\
                # Install the yum requirements defined canonically in the
                # "recipe/yum_requirements.txt" file. After updating that file,
                # run "conda smithy rerender" and this line be updated
                # automatically.
                yum install -y {}


            """.format(' '.join(requirements)))
            forge_config['build_setup'] = build_setup

        # TODO: Conda has a convenience for accessing nested yaml content.
        templates = forge_config.get('templates', {})
        template_name = templates.get('run_docker_build',
                                      'run_docker_build_matrix.tmpl')

        template = jinja_env.get_template(template_name)
        with open(target_fname, 'w') as fh:
            fh.write(template.render(**forge_config))
        st = os.stat(target_fname)
        os.chmod(target_fname, st.st_mode | stat.S_IEXEC)


def render_circle(jinja_env, forge_config, forge_dir):
    meta = forge_config['package']
    with fudge_subdir('linux-64', build_config=meta_config(meta)):
        meta.parse_again()
        matrix = compute_build_matrix(meta, forge_config.get('matrix'))

        cases_not_skipped = []
        for case in matrix:
            pkgs, vars = split_case(case)
            with enable_vars(vars):
                if not ResolvedDistribution(meta, pkgs).skip():
                    cases_not_skipped.append(vars + sorted(pkgs))
        matrix = sorted(cases_not_skipped, key=sort_without_target_arch)

    target_fname = os.path.join(forge_dir, 'circle.yml')
    matrix = prepare_matrix_for_env_vars(matrix)
    forge_config = update_matrix(forge_config, matrix)
    template = jinja_env.get_template('circle.yml.tmpl')
    with open(target_fname, 'w') as fh:
        fh.write(template.render(**forge_config))


@contextmanager
def fudge_subdir(subdir, build_config):
    """
    Override the subdir (aka platform) that conda and conda_build see
    both when fetching the index and in parsing conda build MetaData.

    """
    # Store conda-build and conda.config's existing settings.
    conda_orig = conda.config.subdir
    cb_orig = build_config.subdir

    # Set them to what we want.
    conda.config.subdir = subdir
    build_config.subdir = subdir

    if not hasattr(conda_build, 'api'):
        # Old conda-builds have a copied subdir value, so we need to change that too.
        copied_subdir_orig = conda_build.metadata.subdir
        conda_build.metadata.subdir = subdir

    yield

    # Set them back to what they were
    conda.config.subdir = conda_orig
    build_config.subdir = cb_orig

    if not hasattr(conda_build, 'api'):
        # Old conda-builds have a copied subdir value, so we need to change that too.
        conda_build.metadata.subdir = copied_subdir_orig


def render_travis(jinja_env, forge_config, forge_dir):
    meta = forge_config['package']
    with fudge_subdir('osx-64', build_config=meta_config(meta)):
        meta.parse_again()
        matrix = compute_build_matrix(meta, forge_config.get('matrix'))

        cases_not_skipped = []
        for case in matrix:
            pkgs, vars = split_case(case)
            with enable_vars(vars):
                if not ResolvedDistribution(meta, pkgs).skip():
                    cases_not_skipped.append(vars + sorted(pkgs))
        matrix = sorted(cases_not_skipped, key=sort_without_target_arch)

    target_fname = os.path.join(forge_dir, '.travis.yml')

    if not matrix:
        # There are no cases to build (not even a case without any special
        # dependencies), so remove the .travis.yml if it exists.
        forge_config["travis"]["enabled"] = False
        if os.path.exists(target_fname):
            os.remove(target_fname)
    else:
        forge_config["travis"]["enabled"] = True
        matrix = prepare_matrix_for_env_vars(matrix)
        forge_config = update_matrix(forge_config, matrix)
        template = jinja_env.get_template('travis.yml.tmpl')
        with open(target_fname, 'w') as fh:
            fh.write(template.render(**forge_config))


def render_README(jinja_env, forge_config, forge_dir):
    template = jinja_env.get_template('README.md.tmpl')
    target_fname = os.path.join(forge_dir, 'README.md')
    with open(target_fname, 'w') as fh:
        fh.write(template.render(**forge_config))


class MatrixCaseEnvVar(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __iter__(self):
        # We make the Var iterable so that loops like
        # ``for name, value in cases`` can be used.
        return iter([self.name, self.value])

    def __cmp__(self, other):
        # Implement ordering so that sorting functions as expected.
        if not isinstance(other, type(self)):
            return -3
        elif other.name != self.name:
            return -2
        else:
            return cmp(self.value, other.value)


@contextmanager
def enable_vars(vars):
    existing = {}
    for var in vars:
        if var.name in os.environ:
            existing[var.name] = os.environ[var.name]
        os.environ[var.name] = str(var.value)
    yield
    for var in vars:
        if var.name in existing:
            os.environ[var.name] = existing[var.name]
        else:
            os.environ.pop(var.name)


def split_case(case):
    vars = [item for item in case
            if isinstance(item, MatrixCaseEnvVar)]
    pkgs = [item for item in case
            if not isinstance(item, MatrixCaseEnvVar)]
    return pkgs, vars


def sort_without_target_arch(case):
    arch_order = 0
    python = None
    cmp_case = []
    for name, val in case:
        if name == 'TARGET_ARCH':
            arch_order = {'x86': 1, 'x64': 2}.get(val, 0)
        elif name == 'python':
            # We group all pythons together.
            python = val
        else:
            cmp_case.append([name, val])
    return [python, cmp_case, arch_order]


def render_appveyor(jinja_env, forge_config, forge_dir):
    meta = forge_config['package']
    full_matrix = []
    for platform, arch in [['win-32', 'x86'], ['win-64', 'x64']]:
        with fudge_subdir(platform, build_config=meta_config(meta)):
            meta.parse_again()
            matrix = compute_build_matrix(meta, forge_config.get('matrix'))

            cases_not_skipped = []
            for case in matrix:
                pkgs, vars = split_case(case)
                with enable_vars(vars):
                    if not ResolvedDistribution(meta, pkgs).skip():
                        cases_not_skipped.append(vars + sorted(pkgs))
            if cases_not_skipped:
                arch_env = MatrixCaseEnvVar('TARGET_ARCH', arch)
                full_matrix.extend([arch_env] + list(case)
                                   for case in cases_not_skipped)

    matrix = sorted(full_matrix, key=sort_without_target_arch)

    target_fname = os.path.join(forge_dir, 'appveyor.yml')

    # Clean up any stray `disabled_appveyor.yml` files.
    # This should be removed after everything is re-render
    # with `conda-smithy` version 1.0.0 or later.
    target_fname_disabled = os.path.join(forge_dir, 'disabled_appveyor.yml')
    if os.path.exists(target_fname_disabled):
        os.remove(target_fname_disabled)

    if not matrix:
        # There are no cases to build (not even a case without any special
        # dependencies), so remove the appveyor.yml if it exists.
        forge_config["appveyor"]["enabled"] = False
        if os.path.exists(target_fname):
            os.remove(target_fname)
    else:
        forge_config["appveyor"]["enabled"] = True
        matrix = prepare_matrix_for_env_vars(matrix)
        forge_config = update_matrix(forge_config, matrix)
        template = jinja_env.get_template('appveyor.yml.tmpl')
        with open(target_fname, 'w') as fh:
            fh.write(template.render(**forge_config))


def update_matrix(forge_config, new_matrix):
    """
    Return a new config with the build matrix updated.

    """
    forge_config = forge_config.copy()
    forge_config['matrix'] = new_matrix
    return forge_config


def prepare_matrix_for_env_vars(matrix):
    """
    Turns a matrix with environment variables and pakages into a matrix of
    just environment variables. The package variables are prefixed with CONDA,
    and special cases such as Python and Numpy are handled.

    """
    special_conda_vars = {'python': 'CONDA_PY', 'numpy': 'CONDA_NPY'}
    env_matrix = []
    for case in matrix:
        new_case = []
        for item in case:
            if isinstance(item, MatrixCaseEnvVar):
                new_case.append((item.name, item.value))
            else:
                # We have a package, so transform it into something conda understands.
                name, value = item
                if name in special_conda_vars:
                    name = special_conda_vars[name]
                    value = str(value).replace('.', '')
                else:
                    name = 'CONDA_' + name.upper()
                new_case.append((name, value))
        env_matrix.append(new_case)
    return env_matrix


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
            shutil.copy2(s, d)


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


def compute_build_matrix(meta, existing_matrix=None):
    index = conda.api.get_index()
    mtx = special_case_version_matrix(meta, index)
    mtx = list(filter_cases(mtx, ['python >=2.7,<3|>=3.4', 'numpy >=1.10']))
    if existing_matrix:
        mtx = [tuple(mtx_case) + tuple(MatrixCaseEnvVar(*item) for item in case)
               for case in sorted(existing_matrix)
               for mtx_case in mtx]
    return mtx


def main(forge_file_directory):
    if hasattr(conda_build, 'api'):
        build_config = conda_build.api.Config()
    else:
        build_config = conda_build.config.config

    # conda-build has some really fruity behaviour where it needs CONDA_NPY
    # and CONDA_PY in order to even read a meta. Because we compute version
    # matricies anyway the actual number makes absolutely no difference.
    build_config.CONDA_NPY = '99.9'
    build_config.CONDA_PY = 10

    recipe_dir = 'recipe'
    config = {'docker': {'image': 'condaforge/linux-anvil', 'command': 'bash'},
              'templates': {'run_docker_build': 'run_docker_build_matrix.tmpl'},
              'travis': {},
              'circle': {},
              'appveyor': {},
              'channels': {'sources': ['conda-forge'], 'targets': [['conda-forge', 'main']]},
              'github': {'user_or_org': 'conda-forge', 'repo_name': '', 'branch_name': 'master'},
              'recipe_dir': recipe_dir}
    forge_dir = os.path.abspath(forge_file_directory)

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
    config['package'] = meta = meta_of_feedstock(forge_file_directory, config=build_config)
    if not config['github']['repo_name']:
        config['github']['repo_name'] = meta.name()+'-feedstock'

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
    env = Environment(loader=FileSystemLoader([os.path.join(forge_dir, 'templates'),
                                               tmplt_dir]))

    copy_feedstock_content(forge_dir)

    render_run_docker_build(env, config, forge_dir)
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
