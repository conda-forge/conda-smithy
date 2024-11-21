import collections
import os
import typing
from pathlib import Path

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


class ConfigYAML(typing.NamedTuple):
    workdir: Path
    recipe_name: str
    type: str


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


@pytest.fixture(scope="function", params=["conda-build", "rattler-build"])
def config_yaml(testing_workdir, recipe_dirname, request):
    config = {
        "python": ["2.7", "3.5"],
        "r_base": ["3.3.2", "3.4.2"],
        "python_min": ["2.7"],
    }
    os.makedirs(os.path.join(testing_workdir, recipe_dirname))
    with open(os.path.join(testing_workdir, "config.yaml"), "w") as f:
        f.write("docker:\n")
        f.write("  fallback_image:\n")
        f.write("  - centos:6\n")
    with open(
        os.path.join(testing_workdir, recipe_dirname, "default_config.yaml"),
        "w",
    ) as f:
        if request.param == "conda-build":
            config_name = "conda_build_config.yaml"
            recipe_name = "meta.yaml"
        else:
            config_name = "rattler_build_config.yaml"
            recipe_name = "recipe.yaml"

        yaml.dump(config, f, default_flow_style=False)

        config_path = os.path.abspath(
            os.path.join(
                __file__, "../", "recipes", "default_config", config_name
            )
        )
        config_text = Path(config_path).read_text()

        # need selectors, so write these more manually
        f.write(config_text)

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
        if request.param == "rattler-build":
            config["conda_build_tool"] = "rattler-build"
        yaml.dump(config, f, default_flow_style=False)
    yield ConfigYAML(testing_workdir, recipe_name, request.param)


@pytest.fixture(scope="function")
def noarch_recipe(config_yaml: ConfigYAML, recipe_dirname):
    # get the used params passed for config_yaml fixture
    with open(
        os.path.join(
            config_yaml.workdir, recipe_dirname, config_yaml.recipe_name
        ),
        "w",
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
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, recipe_dirname, "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def noarch_recipe_with_python_min(config_yaml: ConfigYAML, recipe_dirname):
    if config_yaml.type == "rattler-build":
        jinjatxt = "${{ python_min }}"
    else:
        jinjatxt = "{{ python_min }}"
    with open(
        os.path.join(
            config_yaml.workdir, recipe_dirname, config_yaml.recipe_name
        ),
        "w",
    ) as fh:
        fh.write(
            f"""\
package:
    name: python-noarch-test
    version: 1.0.0
build:
    noarch: python
requirements:
    host:
        - python {jinjatxt}
    run:
        - python >={jinjatxt}
    """
        )
    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, recipe_dirname, "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def r_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:

        r_recipe_template_path = os.path.abspath(
            os.path.join(
                __file__, "../", "recipes", "r_recipe", config_yaml.recipe_name
            )
        )
        recipe_template_text = Path(r_recipe_template_path).read_text()

        fh.write(recipe_template_text)

    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def py_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:
        recipe_path = os.path.abspath(
            os.path.join(
                __file__,
                "../",
                "recipes",
                "py_recipe",
                config_yaml.recipe_name,
            )
        )

        content = Path(recipe_path).read_text()
        fh.write(content)

    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def stdlib_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", "meta.yaml"), "w"
    ) as fh:
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
        os.path.join(config_yaml.workdir, "recipe", "stdlib_config.yaml"), "w"
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
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "stdlib_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def stdlib_deployment_target_recipe(config_yaml: ConfigYAML, stdlib_recipe):
    # append to existing stdlib_config.yaml from stdlib_recipe
    with open(
        os.path.join(config_yaml.workdir, "recipe", "stdlib_config.yaml"), "a"
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
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "stdlib_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def upload_on_branch_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:
        recipe_path = os.path.abspath(
            os.path.join(
                __file__,
                "../",
                "recipes",
                "py_recipe",
                config_yaml.recipe_name,
            )
        )

        content = Path(recipe_path).read_text()
        fh.write(content)

    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "conda-forge.yml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def recipe_migration_cfep9(config_yaml: ConfigYAML):
    # write a migrator
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:
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
    """
        )

    os.makedirs(
        os.path.join(config_yaml.workdir, ".ci_support", "migrations"),
        exist_ok=True,
    )
    with open(
        os.path.join(
            config_yaml.workdir, ".ci_support", "migrations", "zlib.yaml"
        ),
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
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def recipe_migration_cfep9_downgrade(
    config_yaml: ConfigYAML, recipe_migration_cfep9
):
    # write a downgrade migrator that lives next to the current migrator.
    # Only this, more recent migrator should apply.
    os.makedirs(
        os.path.join(config_yaml.workdir, ".ci_support", "migrations"),
        exist_ok=True,
    )

    with open(
        os.path.join(
            config_yaml.workdir,
            ".ci_support",
            "migrations",
            "zlib-downgrade.yaml",
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
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def recipe_migration_win_compiled(config_yaml: ConfigYAML, py_recipe):
    os.makedirs(
        os.path.join(config_yaml.workdir, ".ci_support", "migrations"),
        exist_ok=True,
    )
    migration_name = "vc-migrate.yaml"

    with open(
        os.path.join(
            config_yaml.workdir, ".ci_support", "migrations", migration_name
        ),
        "w",
    ) as fh:
        migration_path = os.path.abspath(
            os.path.join(
                __file__, "../", "recipes", "win_migrations", migration_name
            )
        )
        content = Path(migration_path).read_text()
        fh.write(content)

    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def skipped_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:
        recipe_path = os.path.abspath(
            os.path.join(
                __file__,
                "../",
                "recipes",
                "win_skipped_recipes",
                config_yaml.recipe_name,
            )
        )
        content = Path(recipe_path).read_text()
        fh.write(content)

    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def python_skipped_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:
        recipe_path = os.path.abspath(
            os.path.join(
                __file__,
                "../",
                "recipes",
                "python_skipped_recipes",
                config_yaml.recipe_name,
            )
        )
        content = Path(recipe_path).read_text()
        fh.write(content)

    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def linux_skipped_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:
        linux_recipe = os.path.abspath(
            os.path.join(
                __file__,
                "../",
                "recipes",
                "linux_skipped_recipes",
                config_yaml.recipe_name,
            )
        )
        content = Path(linux_recipe).read_text()
        fh.write(content)

    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def render_skipped_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", "meta.yaml"), "w"
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
    with open(
        os.path.join(config_yaml.workdir, "conda-forge.yml"), "a+"
    ) as fh:
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
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def choco_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:
        choco_recipe_path = os.path.abspath(
            os.path.join(
                __file__,
                "../",
                "recipes",
                "choco_recipes",
                config_yaml.recipe_name,
            )
        )
        content = Path(choco_recipe_path).read_text()
        fh.write(content)

    with open(
        os.path.join(config_yaml.workdir, "conda-forge.yml"), "a+"
    ) as fh:
        fh.write(
            """
choco:
    - pkg0
    - pkg1 --version=X.Y.Z
    """
        )
    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def cuda_enabled_recipe(config_yaml: ConfigYAML):
    with open(
        os.path.join(config_yaml.workdir, "recipe", config_yaml.recipe_name),
        "w",
    ) as fh:
        cuda_recipe_path = os.path.abspath(
            os.path.join(
                __file__,
                "../",
                "recipes",
                "cuda_recipes",
                config_yaml.recipe_name,
            )
        )
        content = Path(cuda_recipe_path).read_text()
        fh.write(content)

    return RecipeConfigPair(
        str(config_yaml.workdir),
        _load_forge_config(
            config_yaml.workdir,
            exclusive_config_file=os.path.join(
                config_yaml.workdir, "recipe", "default_config.yaml"
            ),
        ),
    )


@pytest.fixture(scope="function")
def jinja_env():
    tmplt_dir = os.path.join(conda_forge_content, "templates")
    # Load templates from the feedstock in preference to the smithy's templates.
    return SandboxedEnvironment(
        extensions=["jinja2.ext.do"], loader=FileSystemLoader([tmplt_dir])
    )


@pytest.fixture(scope="function")
def v1_noarch_recipe_with_context(testing_workdir: Path, recipe_dirname):
    with open(os.path.join(testing_workdir, "conda-forge.yml"), "w") as f:
        config = {
            "recipe_dir": recipe_dirname,
        }
        config["conda_build_tool"] = "rattler-build"
        yaml.dump(config, f, default_flow_style=False)

    os.mkdir(os.path.join(testing_workdir, recipe_dirname))
    with open(
        os.path.join(testing_workdir, recipe_dirname, "recipe.yaml"),
        "w",
    ) as fh:
        fh.write(
            """
context:
    name: python-noarch-test-from-context
    version: 9.0.0
package:
    name: ${{ name }}
    version: ${{ version }}
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
        testing_workdir,
        _load_forge_config(testing_workdir, exclusive_config_file=None),
    )


@pytest.fixture(scope="function")
def v1_recipe_with_multiple_outputs(testing_workdir: Path, recipe_dirname):
    with open(os.path.join(testing_workdir, "conda-forge.yml"), "w") as f:
        config = {
            "recipe_dir": recipe_dirname,
        }
        config["conda_build_tool"] = "rattler-build"
        yaml.dump(config, f, default_flow_style=False)

    os.mkdir(os.path.join(testing_workdir, recipe_dirname))

    with open(
        os.path.join(testing_workdir, recipe_dirname, "recipe.yaml"),
        "w",
    ) as fh:
        fh.write(
            """
context:
  name: mamba
  mamba_version: "1.5.8"
  libmamba_version: "1.5.9"
  libmambapy_version: "1.5.9"

recipe:
  name: mamba-split
  version: ${{ mamba_version }}

source:
  url: https://github.com/mamba-org/mamba/archive/refs/tags/${{ release }}.tar.gz
  sha256: 6ddaf4b0758eb7ca1250f427bc40c2c3ede43257a60bac54e4320a4de66759a6

build:
  number: 1

outputs:
  - package:
      name: libmamba
      version: ${{ libmamba_version }}

  - package:
      name: libmambapy
      version: ${{ libmambapy_version }}

  - package:
      name: mamba
      version: ${{ mamba_version }}
    """
        )
    return RecipeConfigPair(
        testing_workdir,
        _load_forge_config(testing_workdir, exclusive_config_file=None),
    )
