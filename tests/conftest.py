import collections
import os
from textwrap import dedent

import pytest
import yaml
from conda_build.utils import copy_into
from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment

from conda_smithy.configure_feedstock import (
    _load_forge_config,
    conda_forge_content,
)

RecipeConfigPair = collections.namedtuple(
    "RecipeConfigPair", ("recipe", "config")
)


@pytest.fixture(scope="function")
def testing_workdir(tmpdir, request):
    """Create a workdir in a safe temporary folder; cd into dir above before test, cd out after

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
def recipe_dirname():
    return "recipe"


@pytest.fixture(scope="function")
def config_yaml(testing_workdir, recipe_dirname):
    config = {"python": ["2.7", "3.5"], "r_base": ["3.3.2", "3.4.2"]}
    os.makedirs(os.path.join(testing_workdir, recipe_dirname))
    with open(os.path.join(testing_workdir, "config.yaml"), "w") as f:
        f.write("docker:\n")
        f.write("  fallback_image:\n")
        f.write("  - centos:6\n")
    with open(
        os.path.join(testing_workdir, recipe_dirname, "default_config.yaml"),
        "w",
    ) as f:
        yaml.dump(config, f, default_flow_style=False)
        # need selectors, so write these more manually
        f.write(
            dedent(
                """\
        c_compiler:     # [win]
        - vs2008        # [win]
        - vs2015        # [win]
        vc:             # [win]
        - '9'           # [win]
        - '14'          # [win]
        zip_keys:       # [win]
        - c_compiler    # [win]
        - python        # [win]
        - vc            # [win]
        """
            )
        )
    # dummy file that needs to be present for circle ci.  This is created by the init function
    os.makedirs(os.path.join(testing_workdir, ".circleci"))
    with open(
        os.path.join(testing_workdir, ".circleci", "checkout_merge_commit.sh"),
        "w",
    ) as f:
        f.write("echo dummy file")
    with open(
        os.path.join(testing_workdir, recipe_dirname, "short_config.yaml"), "w"
    ) as f:
        config = {"python": ["2.7"]}
        yaml.dump(config, f, default_flow_style=False)
    with open(
        os.path.join(testing_workdir, recipe_dirname, "long_config.yaml"), "w"
    ) as f:
        config = {"python": ["2.7", "3.5", "3.6"]}
        yaml.dump(config, f, default_flow_style=False)
    with open(os.path.join(testing_workdir, "conda-forge.yml"), "w") as f:
        config = {
            "upload_on_branch": "foo-branch",
            "recipe_dir": recipe_dirname,
        }
        yaml.dump(config, f, default_flow_style=False)
    return testing_workdir


@pytest.fixture(scope="function")
def noarch_recipe(config_yaml, recipe_dirname, request):
    with open(
        os.path.join(config_yaml, recipe_dirname, "meta.yaml"), "w"
    ) as fh:
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
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, recipe_dirname, "default_config.yaml"
            ),
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
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
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
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def stdlib_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
package:
    name: stdlib-test
    version: 1.0.0
requirements:
    build:
        - {{ compiler("c") }}
        - {{ stdlib("c") }}
    host:
        - zlib
about:
    home: home
    """
        )
    with open(
        os.path.join(config_yaml, "recipe", "stdlib_config.yaml"), "w"
    ) as f:
        f.write(
            """\
c_stdlib:
  - sysroot                     # [linux]
  - macosx_deployment_target    # [osx]
  - vs                          # [win]
c_stdlib_version:               # [unix]
  - 2.12                        # [linux64]
  - 2.17                        # [aarch64 or ppc64le]
  - 10.9                        # [osx and x86_64]
  - 11.0                        # [osx and arm64]
"""
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "stdlib_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def stdlib_deployment_target_recipe(config_yaml, stdlib_recipe):
    # append to existing stdlib_config.yaml from stdlib_recipe
    with open(
        os.path.join(config_yaml, "recipe", "stdlib_config.yaml"), "a"
    ) as f:
        f.write(
            """\
MACOSX_DEPLOYMENT_TARGET:       # [osx]
  - 10.14                       # [osx and x86_64]
  - 12.0                        # [osx and arm64]
MACOSX_SDK_VERSION:             # [osx]
  - 10.12                       # [osx and x86_64]
  - 12.0                        # [osx and arm64]
"""
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "stdlib_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def upload_on_branch_recipe(config_yaml, request):
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
            config_yaml,
            exclusive_config_file=os.path.join(config_yaml, "conda-forge.yml"),
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

    os.makedirs(
        os.path.join(config_yaml, ".ci_support", "migrations"), exist_ok=True
    )
    with open(
        os.path.join(config_yaml, ".ci_support", "migrations", "zlib.yaml"),
        "w",
    ) as fh:
        fh.write(
            """
migrator_ts: 1
zlib:
    - 1000
"""
        )

    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def recipe_migration_cfep9_downgrade(config_yaml, recipe_migration_cfep9):
    # write a downgrade migrator that lives next to the current migrator.
    # Only this, more recent migrator should apply.
    os.makedirs(
        os.path.join(config_yaml, ".ci_support", "migrations"), exist_ok=True
    )
    with open(
        os.path.join(
            config_yaml, ".ci_support", "migrations", "zlib-downgrade.yaml"
        ),
        "w",
    ) as fh:
        fh.write(
            """
migrator_ts: 1.0
zlib:
    - 999
"""
        )
    # return recipe_migration_cfep9
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def recipe_migration_win_compiled(config_yaml, py_recipe):
    os.makedirs(
        os.path.join(config_yaml, ".ci_support", "migrations"), exist_ok=True
    )
    with open(
        os.path.join(
            config_yaml, ".ci_support", "migrations", "vc-migrate.yaml"
        ),
        "w",
    ) as fh:
        fh.write(
            dedent(
                """
        migrator_ts: 1.0
        c_compiler:    # [win]
            - vs2008   # [win]
            - vs2017   # [win]
        cxx_compiler:  # [win]
            - vs2008   # [win]
            - vs2017   # [win]
        vc:            # [win]
            - '9'      # [win]
            - '14.1'   # [win]
        zip_keys:
            - - python          # [win]
              - c_compiler      # [win]
              - cxx_compiler    # [win]
              - vc              # [win]
        """
            )
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
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

extra:
    feedstock-name: skip-test-meta
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
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
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
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
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def render_skipped_recipe(config_yaml, request):
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
    with open(os.path.join(config_yaml, "conda-forge.yml"), "a+") as fh:
        fh.write(
            """
skip_render:
    - .gitignore
    - .gitattributes
    - README.md
    - LICENSE.txt
    - .github/workflows
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def choco_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
package:
    name: py-test
    version: 1.0.0
build:
    skip: true  # [not win]
requirements:
    build:
        - {{ compiler('c') }}
    host:
        - python
    run:
        - python
about:
    home: home
    """
        )
    with open(os.path.join(config_yaml, "conda-forge.yml"), "a+") as fh:
        fh.write(
            """
choco:
    - pkg0
    - pkg1 --version=X.Y.Z
    """
        )
    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def cuda_enabled_recipe(config_yaml, request):
    with open(os.path.join(config_yaml, "recipe", "meta.yaml"), "w") as fh:
        fh.write(
            """
package:
    name: py-test
    version: 1.0.0
build:
    skip: True   # [os.environ.get("CF_CUDA_ENABLED") != "True"]
requirements:
    build:
        - {{ compiler('c') }}
        - {{ compiler('cuda') }}
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
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def jinja_env(request):
    tmplt_dir = os.path.join(conda_forge_content, "templates")
    # Load templates from the feedstock in preference to the smithy's templates.
    return SandboxedEnvironment(
        extensions=["jinja2.ext.do"], loader=FileSystemLoader([tmplt_dir])
    )
