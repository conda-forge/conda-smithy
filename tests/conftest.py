import collections
import os

import pytest
import yaml

from jinja2 import Environment, FileSystemLoader
from conda_build.utils import copy_into

from conda_smithy.configure_feedstock import conda_forge_content, _load_forge_config


RecipeConfigPair = collections.namedtuple("RecipeConfigPair", ("recipe", "config"))


@pytest.fixture(scope="function")
def testing_workdir(tmpdir, request):
    """ Create a workdir in a safe temporary folder; cd into dir above before test, cd out after

    :param tmpdir: py.test fixture, will be injected
    :param request: py.test fixture-related, will be injected (see pytest docs)
    """

    saved_path = os.getcwd()

    tmpdir.chdir()
    # temporary folder for profiling output, if any
    tmpdir.mkdir("prof")

    def return_to_saved_path():
        if os.path.isdir(os.path.join(saved_path, "prof")):
            profdir = tmpdir.join("prof")
            files = profdir.listdir("*.prof") if profdir.isdir() else []

            for f in files:
                copy_into(str(f), os.path.join(saved_path, "prof", f.basename))
        os.chdir(saved_path)

    request.addfinalizer(return_to_saved_path)

    return str(tmpdir)


@pytest.fixture(scope="function")
def config_yaml(testing_workdir):
    config = {"python": ["2.7", "3.5"], "r_base": ["3.3.2", "3.4.2"]}
    os.makedirs(os.path.join(testing_workdir, "recipe"))
    with open(os.path.join(testing_workdir, "config.yaml"), "w") as f:
        f.write("docker:\n")
        f.write("  fallback_image:\n")
        f.write("  - centos:6\n")
    with open(os.path.join(testing_workdir, "recipe", "default_config.yaml"), "w") as f:
        yaml.dump(config, f, default_flow_style=False)
        # need selectors, so write these more manually
        f.write("target_platform:\n")
        f.write("- win-64   # [win]\n")
        f.write("- win-32   # [win]\n")
        f.write("c_compiler:\n  # [win]")
        f.write("- vs2008\n  # [win]")
        f.write("- vs2015\n  # [win]")
        f.write("zip_keys:\n  # [win]")
        f.write("- c_compiler\n   # [win]")
        f.write("- python\n   # [win]")
    # dummy file that needs to be present for circle ci.  This is created by the init function
    os.makedirs(os.path.join(testing_workdir, ".circleci"))
    with open(
        os.path.join(testing_workdir, ".circleci", "checkout_merge_commit.sh"), "w"
    ) as f:
        f.write("echo dummy file")
    with open(os.path.join(testing_workdir, "recipe", "short_config.yaml"), "w") as f:
        config = {"python": ["2.7"]}
        yaml.dump(config, f, default_flow_style=False)
    with open(os.path.join(testing_workdir, "recipe", "long_config.yaml"), "w") as f:
        config = {"python": ["2.7", "3.5", "3.6"]}
        yaml.dump(config, f, default_flow_style=False)
    return testing_workdir


@pytest.fixture(scope="function")
def noarch_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
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
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml, exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml")
        ),
    )


@pytest.fixture(scope="function")
def r_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
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
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml, exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml")
        ),
    )


@pytest.fixture(scope="function")
def py_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
package:
    name: py-test
    version: 1.0.0
requirements:
    build:                      # [win]
        - {{ compiler('c') }}   # [win]
    host:
        - python
    run:
        - python
about:
    home: home
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml, exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml")
        ),
    )


@pytest.fixture(scope="function")
def recipe_migration_cfep9(config_yaml, request):
    # write a migrator
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
package:
    name: py-test
    version: 1.0.0
requirements:
    host:
        - python
        - zlib
    run:
        - python
about:
    home: home
    """
        )

    os.mkdir(os.path.join(config_yaml, "migrations"))
    with open(os.path.join(config_yaml, "migrations", "zlib.yaml"), "w") as fh:
        fh.write("""
zlib:
    - 1000
""")

    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml, exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml")
        ),
    )


@pytest.fixture(scope="function")
def recipe_migration_cfep9_downgrade(config_yaml, recipe_migration_cfep9):
    # write a downgrade migrator that lives next to the current migrator.
    # Only this, more recent migrator should apply.
    with open(os.path.join(config_yaml, "migrations", "zlib-downgrade.yaml"), "w") as fh:
        fh.write("""
migration_ts: 1.0
zlib:
    - 999
""")
    #return recipe_migration_cfep9
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml, exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml")
        ),
    )



@pytest.fixture(scope="function")
def skipped_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
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
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml, exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml")
        ),
    )


@pytest.fixture(scope="function")
def python_skipped_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
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
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml, exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml")
        ),
    )


@pytest.fixture(scope="function")
def linux_skipped_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
package:
    name: py-test
    version: 1.0.0
build:
    skip: True   # [linux]
requirements:
    build:
        - zlib
about:
    home: home
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml, exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml")
        ),
    )


@pytest.fixture(scope="function")
def jinja_env(request):
    tmplt_dir = os.path.join(conda_forge_content, "templates")
    # Load templates from the feedstock in preference to the smithy's templates.
    return Environment(
        extensions=["jinja2.ext.do"], loader=FileSystemLoader([tmplt_dir])
    )
