import os
import conda_smithy.configure_feedstock as cnfgr_fdstk

import pytest
import copy


def test_noarch_skips_appveyor(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_appveyor(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    # this configuration should be skipped
    assert not noarch_recipe.config["appveyor"]["enabled"]
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    assert not os.path.isdir(os.path.join(noarch_recipe.recipe, ".ci_support"))


def test_noarch_skips_travis(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_travis(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    # this configuration should be skipped
    assert not noarch_recipe.config["travis"]["enabled"]
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    assert not os.path.isdir(os.path.join(noarch_recipe.recipe, ".ci_support"))


def test_noarch_runs_on_circle(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    # this configuration should be run
    assert noarch_recipe.config["circle"]["enabled"]
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(noarch_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 1


def test_r_skips_appveyor(r_recipe, jinja_env):
    cnfgr_fdstk.render_appveyor(
        jinja_env=jinja_env,
        forge_config=r_recipe.config,
        forge_dir=r_recipe.recipe,
    )
    # this configuration should be skipped
    assert not r_recipe.config["appveyor"]["enabled"]
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    assert not os.path.isdir(os.path.join(r_recipe.recipe, ".ci_support"))


def test_r_matrix_travis(r_recipe, jinja_env):
    cnfgr_fdstk.render_travis(
        jinja_env=jinja_env,
        forge_config=r_recipe.config,
        forge_dir=r_recipe.recipe,
    )
    # this configuration should be run
    assert r_recipe.config["travis"]["enabled"]
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(r_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_r_matrix_on_circle(r_recipe, jinja_env):
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=r_recipe.config,
        forge_dir=r_recipe.recipe,
    )
    # this configuration should be run
    assert r_recipe.config["circle"]["enabled"]
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(r_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_py_matrix_appveyor(py_recipe, jinja_env):
    cnfgr_fdstk.render_appveyor(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    # this configuration should be skipped
    assert py_recipe.config["appveyor"]["enabled"]
    matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # 2 python versions, 2 target_platforms.  Recipe uses c_compiler, but this is a zipped key
    #     and shouldn't add extra configurations
    assert len(os.listdir(matrix_dir)) == 4


def test_py_matrix_travis(py_recipe, jinja_env):
    cnfgr_fdstk.render_travis(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    # this configuration should be run
    assert py_recipe.config["travis"]["enabled"]
    matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # two matrix enties - one per py ver
    assert len(os.listdir(matrix_dir)) == 2


def test_py_matrix_on_circle(py_recipe, jinja_env):
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    # this configuration should be run
    assert py_recipe.config["circle"]["enabled"]
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_circle_with_yum_reqs(py_recipe, jinja_env):
    with open(
        os.path.join(py_recipe.recipe, "recipe", "yum_requirements.txt"), "w"
    ) as f:
        f.write("nano\n")
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )


def test_circle_osx(py_recipe, jinja_env):
    forge_dir = py_recipe.recipe
    travis_yml_file = os.path.join(forge_dir, ".travis.yml")
    circle_osx_file = os.path.join(forge_dir, ".circleci", "run_osx_build.sh")
    circle_linux_file = os.path.join(
        forge_dir, ".circleci", "run_docker_build.sh"
    )
    circle_config_file = os.path.join(forge_dir, ".circleci", "config.yml")

    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env, forge_config=py_recipe.config, forge_dir=forge_dir
    )
    assert not os.path.exists(circle_osx_file)
    assert os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)
    cnfgr_fdstk.render_travis(
        jinja_env=jinja_env, forge_config=py_recipe.config, forge_dir=forge_dir
    )
    assert os.path.exists(travis_yml_file)

    config = copy.deepcopy(py_recipe.config)
    config["provider"]["osx"] = "circle"
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env, forge_config=config, forge_dir=forge_dir
    )
    assert os.path.exists(circle_osx_file)
    assert os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)
    cnfgr_fdstk.render_travis(
        jinja_env=jinja_env, forge_config=config, forge_dir=forge_dir
    )
    assert not os.path.exists(travis_yml_file)

    config = copy.deepcopy(py_recipe.config)
    config["provider"]["linux"] = "dummy"
    config["provider"]["osx"] = "circle"
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env, forge_config=config, forge_dir=forge_dir
    )
    assert os.path.exists(circle_osx_file)
    assert not os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)


def test_circle_skipped(linux_skipped_recipe, jinja_env):
    forge_dir = linux_skipped_recipe.recipe
    circle_osx_file = os.path.join(forge_dir, ".circleci", "run_osx_build.sh")
    circle_linux_file = os.path.join(
        forge_dir, ".circleci", "run_docker_build.sh"
    )
    circle_config_file = os.path.join(forge_dir, ".circleci", "config.yml")

    cnfgr_fdstk.copy_feedstock_content(forge_dir)
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=linux_skipped_recipe.config,
        forge_dir=forge_dir,
    )
    assert not os.path.exists(circle_osx_file)
    assert not os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)

    config = copy.deepcopy(linux_skipped_recipe.config)
    config["provider"]["osx"] = "circle"

    cnfgr_fdstk.copy_feedstock_content(forge_dir)
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env, forge_config=config, forge_dir=forge_dir
    )
    assert os.path.exists(circle_osx_file)
    assert not os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)


def test_render_with_all_skipped_generates_readme(skipped_recipe, jinja_env):
    cnfgr_fdstk.render_README(
        jinja_env=jinja_env,
        forge_config=skipped_recipe.config,
        forge_dir=skipped_recipe.recipe,
    )


def test_render_windows_with_skipped_python(python_skipped_recipe, jinja_env):
    config = python_skipped_recipe.config
    config["exclusive_config_file"] = os.path.join(
        python_skipped_recipe.recipe, "long_config.yaml"
    )
    cnfgr_fdstk.render_appveyor(
        jinja_env=jinja_env,
        forge_config=config,
        forge_dir=python_skipped_recipe.recipe,
    )
    # this configuration should be skipped
    assert python_skipped_recipe.config["appveyor"]["enabled"]

    matrix_dir = os.path.join(python_skipped_recipe.recipe, ".ci_support")
    # matrix has 2.7, 3.5, 3.6, but 3.6 is skipped.  Should be 2 entries.
    assert len(os.listdir(matrix_dir)) == 2


def test_readme_has_terminating_newline(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_README(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    readme_path = os.path.join(noarch_recipe.recipe, "README.md")
    assert os.path.exists(readme_path)
    with open(readme_path, "rb") as readme_file:
        readme_file.seek(-1, os.SEEK_END)
        assert readme_file.read() == b"\n"
