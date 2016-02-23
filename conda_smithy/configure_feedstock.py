from __future__ import print_function

import os
from os.path import join, isdir
import shutil
import stat
import yaml
import warnings

import conda.api
from conda.resolve import MatchSpec
from conda_build.metadata import MetaData
from conda_build_all.version_matrix import special_case_version_matrix, filter_cases
from jinja2 import Environment, FileSystemLoader


conda_forge_content = os.path.abspath(os.path.dirname(__file__))


def render_run_docker_build(jinja_env, forge_config, forge_dir):
    # TODO: Conda has a convenience for accessing nested yaml content.
    template_name = forge_config.get('templates', {}).get('run_docker_build',
                                                    'run_docker_build_matrix.tmpl')
    template = jinja_env.get_template(template_name)
    run_docker_build_fname = os.path.join(forge_dir, 'ci_support', 'run_docker_build.sh')
    with open(run_docker_build_fname, 'w') as fh:
        fh.write(template.render(**forge_config))
    st = os.stat(run_docker_build_fname)
    os.chmod(run_docker_build_fname, st.st_mode | stat.S_IEXEC)


def render_travis(jinja_env, forge_config, forge_dir):
    template = jinja_env.get_template('travis.yml.tmpl')
    target_fname = os.path.join(forge_dir, '.travis.yml')
    with open(target_fname, 'w') as fh:
        fh.write(template.render(**forge_config))


def render_README(jinja_env, forge_config, forge_dir):
    template = jinja_env.get_template('README.md.tmpl')
    target_fname = os.path.join(forge_dir, 'README.md')
    with open(target_fname, 'w') as fh:
        fh.write(template.render(**forge_config))

def render_recipes_README(jinja_env, forge_config, forge_dir):
    template = jinja_env.get_template('recipes_README.md.tmpl')
    target_fname = os.path.join(forge_dir, 'recipes', 'README.md')
    with open(target_fname, 'w') as fh:
        fh.write(template.render(**forge_config))


def render_appveyor(jinja_env, forge_config, forge_dir):
    template = jinja_env.get_template('appveyor.yml.tmpl')
    target_fname = os.path.join(forge_dir, 'appveyor.yml')
    with open(target_fname, 'w') as fh:
        fh.write(template.render(**forge_config))


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


def copy_feedstock_content(forge_dir, is_multi=False):
    feedstock_content = os.path.join(conda_forge_content,
                                     'feedstock_content')
    ignore = ['README']
    if is_multi:
        ignore.append(os.path.join('ci_support', 'upload_or_check_non_existence.py'))
    copytree(feedstock_content, forge_dir, ignore)


def meta_of_feedstock(forge_dir):
    recipe_dir = 'recipe'
    meta_dir = os.path.join(forge_dir, recipe_dir)
    if not os.path.exists(meta_dir):
        raise IOError("The given directory isn't a feedstock.")
    meta = MetaData(meta_dir)
    return meta


def compute_build_matrix(meta):
    index = conda.api.get_index()
    mtx = special_case_version_matrix(meta, index)
    mtx = list(filter_cases(mtx, ['python >=2.7,<3|>=3.4', 'numpy >=1.9']))
    return mtx


def main(forge_file_directory):
    config = {'is_multi': False,
              'recipe_dir': "recipe",
              'docker': {'image': 'pelson/obvious-ci:latest_x64', 'command': 'bash'},
              'templates': {'run_docker_build': 'run_docker_build_matrix.tmpl'},
              'travis': [],
              'circle': [],
              'appveyor': [],
              'channels': {'sources': ['conda-forge'], 'targets': [['conda-forge', 'main']]},
              'github': {'user_or_org': '<unconfigured>', 'repo_name': '<unconfigured>'}
              }
    forge_dir = os.path.abspath(forge_file_directory)

    forge_yml = os.path.join(forge_dir, "conda-forge.yml")
    if not os.path.exists(forge_yml):
        warnings.warn('No conda-forge.yml found. Assuming default options.')
    else:
        with open(forge_yml, "r") as fh:
            file_config = list(yaml.load_all(fh))[0]
        # The config is just the union of the defaults, and the overriden
        # values. (XXX except dicts within dicts need to be dealt with!)
        config.update(file_config)
        if not 'github' in file_config:
            print("github values not present in conda-forge.yml: please add 'github.user_or_org' "
                  "and 'github.repo_name' settings or rerun 'conda smithy register-github ...'.")
    if not config['is_multi']:
        config['package'] = meta = meta_of_feedstock(forge_file_directory)
    else:
        d = join(forge_dir, 'recipes')
        recipes = [join(d, s) for s in os.listdir(d) if isdir(join(d, s))]
        recipes_meta = [MetaData(d) for d in recipes]
        config['packages'] = recipes_meta

    tmplt_dir = os.path.join(conda_forge_content, 'templates')
    # Load templates from the feedstock in preference to the smithy's templates.
    env = Environment(loader=FileSystemLoader([os.path.join(forge_dir, 'templates'),
                                               tmplt_dir]))

    copy_feedstock_content(forge_dir, config['is_multi'])
    render_run_docker_build(env, config, forge_dir)
    render_travis(env, config, forge_dir)
    render_appveyor(env, config, forge_dir)
    render_README(env, config, forge_dir)
    if config['is_multi']:
        render_recipes_README(env, config, forge_dir)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=('Configure a feedstock given '
                                                  'a conda-forge.yml file.'))
    parser.add_argument('forge_file_directory',
                        help=('the directory containing the conda-forge.yml file '
                              'used to configure the feedstock'))

    args = parser.parse_args()
    main(args.forge_file_directory)
