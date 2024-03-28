import collections
import os
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from jinja2 import Environment, FileSystemLoader
from conda_build.utils import copy_into

from conda_smithy.configure_feedstock import (
    conda_forge_content,
    _load_forge_config,
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


@pytest.fixture(scope="function", params=["conda-build", "rattler-build"])
def config_yaml(testing_workdir, recipe_dirname, request):
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
        if request.param == "conda-build":
            config_name = "conda_build_config.yaml"
        else:
            config_name = "rattler_build_config.yaml"
            config["python"] = ["3.8", "3.10"]
            config["r_base"] = ["4.2", "4.3"]

        yaml.dump(config, f, default_flow_style=False)
        
        config_path = os.path.abspath(os.path.join(__file__, '../', 'recipes', 'default_config', config_name))
        config_text =  Path(config_path).read_text()

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
        if request.param == "rattler-build":
            config = {"python": ["3.8"]}
        else:
            config = {"python": ["2.7"]}

        yaml.dump(config, f, default_flow_style=False)
    with open(
        os.path.join(testing_workdir, recipe_dirname, "long_config.yaml"), "w"
    ) as f:
        if request.param == "rattler-build":
            config = {"python": ["3.6", "3.8", "3.10"]}
        else:
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
    yield testing_workdir


@pytest.fixture(scope="function")
def noarch_recipe(config_yaml, recipe_dirname, request):
    # get the used params passed for config_yaml fixture
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "rattler-build":
        recipe_name = "recipe.yaml"
    else:
        recipe_name = "meta.yaml"

    with open(
        os.path.join(config_yaml, recipe_dirname, recipe_name), "w"
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
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "rattler-build":
        recipe_name = "recipe.yaml"
    else:
        recipe_name = "meta.yaml"


    with open(os.path.join(config_yaml, "recipe", recipe_name), "w") as fh:
        
        r_recipe_template_path = os.path.abspath(os.path.join(__file__, "../", "recipes", "r_recipe", recipe_name))
        recipe_template_text = Path(r_recipe_template_path).read_text()
        
        fh.write(recipe_template_text)

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
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    
    if config_yaml_param_value == "conda-build":
        recipe_name = "meta.yaml"
    else:
        recipe_name = "recipe.yaml"

    with open(os.path.join(config_yaml, "recipe", recipe_name), "w") as fh:
        recipe_path = os.path.abspath(os.path.join(__file__, '../', 'recipes', 'py_recipe', recipe_name))

        content = Path(recipe_path).read_text()
        fh.write(content)

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
def upload_on_branch_recipe(config_yaml, request):
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "conda-build":
        recipe_name = "meta.yaml"
    else:
        recipe_name = "recipe.yaml"

    with open(os.path.join(config_yaml, "recipe", recipe_name), "w") as fh:
        recipe_path = os.path.abspath(os.path.join(__file__, '../', 'recipes', 'py_recipe', recipe_name))

        content = Path(recipe_path).read_text()
        fh.write(content)


    return RecipeConfigPair(
        str(config_yaml),
        _load_forge_config(
            config_yaml,
            exclusive_config_file=os.path.join(config_yaml, "conda-forge.yml"),
        ),
    )


@pytest.fixture(scope="function")
def recipe_migration_cfep9(config_yaml, request):
    about_home = """
about:
    home: home
"""
    additional_requirement = ""
    
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "conda-build":
        recipe_name = "meta.yaml"
        zlib_value = "1000"
    else:
        recipe_name = "recipe.yaml"
        about_home = ""
        zlib_value = "1.2.12" 
        additional_requirement = "- ruby"

    
    # write a migrator
    with open(os.path.join(config_yaml, "recipe", recipe_name), "w") as fh:
        fh.write(
            f"""
package:
    name: py-test
    version: 1.0.0
requirements:
    host:
        - python
        - zlib
        {additional_requirement}
    run:
        - python
{about_home}
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
            f"""
migrator_ts: 1
zlib:
    - {zlib_value}
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
def recipe_migration_cfep9_downgrade(config_yaml, recipe_migration_cfep9, request):
    # write a downgrade migrator that lives next to the current migrator.
    # Only this, more recent migrator should apply.
    os.makedirs(
        os.path.join(config_yaml, ".ci_support", "migrations"), exist_ok=True
    )
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "conda-build":
        zlib_value = "999"
    else:
        zlib_value = "1.2.11" 
    with open(
        os.path.join(
            config_yaml, ".ci_support", "migrations", "zlib-downgrade.yaml"
        ),
        "w",
    ) as fh:
        fh.write(
            f"""
migrator_ts: 1.0
zlib:
    - {zlib_value}
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
def recipe_migration_win_compiled(config_yaml, py_recipe, request):
    os.makedirs(
        os.path.join(config_yaml, ".ci_support", "migrations"), exist_ok=True
    )
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "conda-build":
        migration_name = "vc-migrate.yaml"
    else:
        migration_name = "ruby-migrate.yaml"

    with open(
        os.path.join(
            config_yaml, ".ci_support", "migrations", migration_name
        ),
        "w",
    ) as fh:
        migration_path = os.path.abspath(os.path.join(__file__, '../', 'recipes', 'win_migrations', migration_name))
        content = Path(migration_path).read_text()
        fh.write(content)


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
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "rattler-build":
        recipe_name = "recipe.yaml"
    else:
        recipe_name = "meta.yaml"

    with open(os.path.join(config_yaml, "recipe", recipe_name), "w") as fh:        
        recipe_path = os.path.abspath(os.path.join(__file__, '../', 'recipes', 'win_skipped_recipes', recipe_name))
        content = Path(recipe_path).read_text()
        fh.write(content)


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
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "rattler-build":
        recipe_name = "recipe.yaml"
    else:
        recipe_name = "meta.yaml"
    

    with open(os.path.join(config_yaml, "recipe", recipe_name), "w") as fh:
        recipe_path = os.path.abspath(os.path.join(__file__, '../', 'recipes', 'python_skipped_recipes', recipe_name))
        content = Path(recipe_path).read_text()
        fh.write(content)

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
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "rattler-build":
        recipe_name = "recipe.yaml"
    else:
        recipe_name = "meta.yaml"
    
    
    
    with open(os.path.join(config_yaml, "recipe", recipe_name), "w") as fh:
        linux_recipe = os.path.abspath(os.path.join(__file__, '../', 'recipes', 'linux_skipped_recipes', recipe_name))
        content = Path(linux_recipe).read_text()
        fh.write(content)

    
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
    config_yaml_param_value = request.node.callspec.params['config_yaml']
    if config_yaml_param_value == "conda-build":
        recipe_name = "meta.yaml"
    else:
        recipe_name = "recipe.yaml"
    
    with open(os.path.join(config_yaml, "recipe", recipe_name), "w") as fh:
        choco_recipe_path = os.path.abspath(os.path.join(__file__, '../', 'recipes', 'choco_recipes', recipe_name))
        content = Path(choco_recipe_path).read_text()
        fh.write(content)

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
    return Environment(
        extensions=["jinja2.ext.do"], loader=FileSystemLoader([tmplt_dir])
    )
