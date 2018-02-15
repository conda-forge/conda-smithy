import collections
import os

import pytest
import yaml

from jinja2 import Environment, FileSystemLoader
from conda_build.utils import copy_into

from conda_smithy.configure_feedstock import conda_forge_content, _load_forge_config


RecipeConfigPair = collections.namedtuple('RecipeConfigPair', ('recipe', 'config'))


@pytest.fixture(scope='function')
def testing_workdir(tmpdir, request):
    """ Create a workdir in a safe temporary folder; cd into dir above before test, cd out after

    :param tmpdir: py.test fixture, will be injected
    :param request: py.test fixture-related, will be injected (see pytest docs)
    """

    saved_path = os.getcwd()

    tmpdir.chdir()
    # temporary folder for profiling output, if any
    tmpdir.mkdir('prof')

    def return_to_saved_path():
        if os.path.isdir(os.path.join(saved_path, 'prof')):
            profdir = tmpdir.join('prof')
            files = profdir.listdir('*.prof') if profdir.isdir() else []

            for f in files:
                copy_into(str(f), os.path.join(saved_path, 'prof', f.basename))
        os.chdir(saved_path)

    request.addfinalizer(return_to_saved_path)

    return str(tmpdir)


@pytest.fixture(scope='function')
def config_yaml(testing_workdir):
    config = {
        'python': ['2.7', '3.5'],
        'r_base': ['3.3.2', '3.4.2'],
    }
    with open(os.path.join(testing_workdir, 'config.yaml'), 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
        # need selectors, so write these more manually
        f.write('target_platform:\n')
        f.write('- win-64   # [win]\n')
        f.write('- win-32   # [win]\n')
    # dummy file that needs to be present for circle ci.  This is created by the init function
    os.makedirs(os.path.join(testing_workdir, '.circleci'))
    with open(os.path.join(testing_workdir, '.circleci', 'checkout_merge_commit.sh'), 'w') as f:
        f.write('echo dummy file')
    with open(os.path.join(testing_workdir, 'short_config.yaml'), 'w') as f:
        config = {
            'python': ['2.7'],
        }
        yaml.dump(config, f, default_flow_style=False)
    with open(os.path.join(testing_workdir, 'long_config.yaml'), 'w') as f:
        config = {
            'python': ['2.7', '3.5', '3.6'],
        }
        yaml.dump(config, f, default_flow_style=False)
    return testing_workdir


@pytest.fixture(scope='function')
def noarch_recipe(config_yaml, request):
    os.makedirs(os.path.join(config_yaml, 'recipe'))
    with open(os.path.join(config_yaml, 'recipe', 'meta.yaml'), 'w') as fh:
        fh.write("""
package:
    name: python-noarch-test
    version: 1.0.0
build:
    noarch: python
requirements:
    build:
        - python
    run:
        - python
    """)
    return RecipeConfigPair(str(config_yaml),
                            _load_forge_config(config_yaml,
                            variant_config_files=[os.path.join(config_yaml,
                                                               'config.yaml')]))


@pytest.fixture(scope='function')
def r_recipe(config_yaml, request):
    os.makedirs(os.path.join(config_yaml, 'recipe'))
    with open(os.path.join(config_yaml, 'recipe', 'meta.yaml'), 'w') as fh:
        fh.write("""
package:
    name: r-test
    version: 1.0.0
build:
    skip: True  # [win]
requirements:
    build:
        - r-base
    run:
        - r-base
    """)
    return RecipeConfigPair(str(config_yaml),
                            _load_forge_config(config_yaml,
                                               variant_config_files=[os.path.join(config_yaml,
                                                                                  'config.yaml')]))


@pytest.fixture(scope='function')
def py_recipe(config_yaml, request):
    os.makedirs(os.path.join(config_yaml, 'recipe'))
    with open(os.path.join(config_yaml, 'recipe', 'meta.yaml'), 'w') as fh:
        fh.write("""
package:
    name: py-test
    version: 1.0.0
requirements:
    build:
        - python
    run:
        - python
about:
    home: home
    """)
    return RecipeConfigPair(str(config_yaml),
                            _load_forge_config(config_yaml,
                                               variant_config_files=[os.path.join(config_yaml,
                                                                                  'config.yaml')]))


@pytest.fixture(scope='function')
def skipped_recipe(config_yaml, request):
    os.makedirs(os.path.join(config_yaml, 'recipe'))
    with open(os.path.join(config_yaml, 'recipe', 'meta.yaml'), 'w') as fh:
        fh.write("""
package:
    name: skip-test
    version: 1.0.0
build:
    skip: True
requirements:
    build:
        - python
    run:
        - python
about:
    home: home
    """)
    return RecipeConfigPair(str(config_yaml),
                            _load_forge_config(config_yaml,
                                               variant_config_files=[os.path.join(config_yaml,
                                                                                  'config.yaml')]))

@pytest.fixture(scope='function')
def python_skipped_recipe(config_yaml, request):
    os.makedirs(os.path.join(config_yaml, 'recipe'))
    with open(os.path.join(config_yaml, 'recipe', 'meta.yaml'), 'w') as fh:
        fh.write("""
package:
    name: py-test
    version: 1.0.0
build:
    skip: True   # [py36]
requirements:
    build:
        - python
    run:
        - python
about:
    home: home
    """)
    return RecipeConfigPair(str(config_yaml),
                            _load_forge_config(config_yaml,
                                               variant_config_files=[os.path.join(config_yaml,
                                                                                  'config.yaml')]))


@pytest.fixture(scope='function')
def jinja_env(request):
    tmplt_dir = os.path.join(conda_forge_content, 'templates')
    # Load templates from the feedstock in preference to the smithy's templates.
    return Environment(extensions=['jinja2.ext.do'], loader=FileSystemLoader([tmplt_dir]))
