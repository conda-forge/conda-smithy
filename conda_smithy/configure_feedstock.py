#!/usr/bin/env python
from __future__ import print_function
from jinja2 import Environment, FileSystemLoader
import os
import stat
import yaml
import warnings

from conda_build.metadata import MetaData
from conda.resolve import MatchSpec


__version__ = '0.1.0'

conda_forge_content = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def about_template():
    return '# This file was generated automatically by conda-forge (vn {}).'.format(__version__)


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
        fh.write(about_template())
        fh.write(template.render(**forge_config))


def render_README(jinja_env, forge_config, forge_dir):
    template = jinja_env.get_template('README.tmpl')
    target_fname = os.path.join(forge_dir, 'README')
    with open(target_fname, 'w') as fh:
        fh.write(template.render(**forge_config))


def render_appveyor(jinja_env, forge_config, forge_dir):
    template = jinja_env.get_template('appveyor.yml.tmpl')
    target_fname = os.path.join(forge_dir, 'appveyor.yml')
    with open(target_fname, 'w') as fh:
        fh.write(about_template())
        fh.write(template.render(**forge_config))


import shutil
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
    copytree(feedstock_content, forge_dir, 'README')



full_matrix = [{'python': '2.7', 'numpy': '1.8'},
               {'python': '2.7', 'numpy': '1.9'},
               {'python': '3.5', 'numpy': '1.9'},
               ]

def compute_build_matrix(meta, special_versions=None):
    # Create match specs, without conda clobbering various versions (such as numpy + python)
    build_deps = [MatchSpec(spec) for spec in meta.get_value('requirements/build', [])]
#     build_deps = meta.ms_depends('build')
    dep_names = [ms.name for ms in build_deps]
    if special_versions is None:
        special_versions = {'python': ['2.7', '3.4'],
                            'numpy': ['1.8', '1.9']}

    # Sometimes we put a numpy dependency in, without explicitly stating that we depend on python.
    # Handle this case.
    if 'numpy' in dep_names and 'python' not in dep_names:
        meta.get_section('requirements').setdefault('build', []).append('python >2.3')
        build_deps = meta.ms_depends('build')
        dep_names = [ms.name for ms in meta.ms_depends('build')]

    # Remove any special versions which aren't important here.
    for special_item in list(special_versions.keys()):
        if special_item not in dep_names:
            special_versions.pop(special_item)
        else:
            # Ensure that the iterable of versions is mutable.
            special_versions[special_item] = list(special_versions[special_item])

    for dependency_name, possible_versions in special_versions.items():
        for match_spec in build_deps:
            if match_spec.name == dependency_name:
                for version in possible_versions[:]:
                    suitable_version = all(version_spec.match(version)
                                           for version_spec in getattr(match_spec, 'vspecs', []))
                    if not suitable_version:
                        possible_versions.remove(version)
    import itertools

    # Expand the each version into a (name, version) pair.
    versions = [[(name, version) for version in versions]
                for name, versions in special_versions.items()]
    matrix = list(itertools.product(*versions))
    return matrix


# def build_matrix_to_env_variables(matrix):
#     cases = {'python': 'CONDA_PY', 'numpy': 'CONDA_NPY'}
#     variables = []
#     for case in matrix:
#         vars = [[cases.get(name, name), version] for name, version in case]
#         variables.append(vars)
#     return matrix


def meta_of_feedstock(forge_dir):
    recipe_dir = 'recipe'
    meta_dir = os.path.join(forge_dir, recipe_dir)
    meta = MetaData(meta_dir)
    return meta


def main(forge_file_directory):
    recipe_dir = 'recipe'
    config = {'docker': {'image': 'pelson/conda64_obvious_ci', 'command': 'bash'},
              'templates': {'run_docker_build': 'run_docker_build.tmpl'},
              'travis': [],
              'circle': [],
              'appveyor': [],
              'channels': {'sources': [], 'target': []},
              'recipe_dir': recipe_dir}
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

    config['package'] = meta = meta_of_feedstock(forge_file_directory)

    matrix = compute_build_matrix(meta)
#     matrix.append([('foo', '1')])
#     print(matrix)
    # TODO: Allow the forge.yml to filter the matrix.
    # TODO: What if no matrix items are figured out, and the template is matrix oriented? And visa-versa.
    if matrix:
        config['matrix'] = matrix

    tmplt_dir = os.path.join(conda_forge_content, 'templates')
    # Load templates from the feedstock in preference to the smithy's templates.
    env = Environment(loader=FileSystemLoader([os.path.join(forge_dir, 'templates'),
                                               tmplt_dir]))

    copy_feedstock_content(forge_dir)
    render_run_docker_build(env, config, forge_dir)
    render_travis(env, config, forge_dir)
    render_appveyor(env, config, forge_dir)
    render_README(env, config, forge_dir)


if True and __name__ == '__main__':
    main('../udunits-feedstock')
    main('../libmo_unpack-feedstock')
    main('../mo_pack-feedstock')

elif __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=('Configure a feedstock given '
                                                  'a conda-forge.yml file.'))
    parser.add_argument('forge_file_directory',
                        help=('the directory containing the conda-forge.yml file '
                              'used to configure the feedstock'))

    args = parser.parse_args()
    main(args.forge_file_directory)
