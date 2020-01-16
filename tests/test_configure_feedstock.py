import os
import conda_smithy.configure_feedstock as cnfgr_fdstk

import pytest
import copy
import yaml


def test_noarch_skips_appveyor(noarch_recipe, jinja_env):
    noarch_recipe.config["provider"]["win"] = "appveyor"
    cnfgr_fdstk.render_appveyor(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    # this configuration should be skipped
    assert not noarch_recipe.config["appveyor"]["enabled"]
    assert not os.path.isdir(os.path.join(noarch_recipe.recipe, ".ci_support"))


def test_noarch_skips_travis(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_travis(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    # this configuration should be skipped
    assert not noarch_recipe.config["travis"]["enabled"]
    assert not os.path.isdir(os.path.join(noarch_recipe.recipe, ".ci_support"))


@pytest.mark.legacy_circle
def test_noarch_runs_on_circle(noarch_recipe, jinja_env):
    noarch_recipe.config["provider"]["linux"] = "circle"

    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )

    # this configuration should be run
    assert noarch_recipe.config["circle"]["enabled"]
    matrix_dir = os.path.join(noarch_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 1


def test_noarch_runs_on_azure(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_azure(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    # this configuration should be run
    assert noarch_recipe.config["azure"]["enabled"]
    matrix_dir = os.path.join(noarch_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 1


def test_r_skips_appveyor(r_recipe, jinja_env):
    r_recipe.config["provider"]["win"] = "appveyor"
    cnfgr_fdstk.render_appveyor(
        jinja_env=jinja_env,
        forge_config=r_recipe.config,
        forge_dir=r_recipe.recipe,
    )
    # this configuration should be skipped
    assert not r_recipe.config["appveyor"]["enabled"]
    assert not os.path.isdir(os.path.join(r_recipe.recipe, ".ci_support"))


@pytest.mark.legacy_travis
def test_r_matrix_travis(r_recipe, jinja_env):
    r_recipe.config["provider"]["osx"] = "travis"

    cnfgr_fdstk.render_travis(
        jinja_env=jinja_env,
        forge_config=r_recipe.config,
        forge_dir=r_recipe.recipe,
    )
    # this configuration should be run
    assert r_recipe.config["travis"]["enabled"]
    matrix_dir = os.path.join(r_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


@pytest.mark.legacy_circle
def test_r_matrix_on_circle(r_recipe, jinja_env):
    r_recipe.config["provider"]["linux"] = "circle"

    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=r_recipe.config,
        forge_dir=r_recipe.recipe,
    )
    # this configuration should be run
    assert r_recipe.config["circle"]["enabled"]
    matrix_dir = os.path.join(r_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_r_matrix_azure(r_recipe, jinja_env):
    cnfgr_fdstk.render_azure(
        jinja_env=jinja_env,
        forge_config=r_recipe.config,
        forge_dir=r_recipe.recipe,
    )
    # this configuration should be run
    assert r_recipe.config["azure"]["enabled"]
    matrix_dir = os.path.join(r_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 4


def test_py_matrix_appveyor(py_recipe, jinja_env):
    py_recipe.config["provider"]["win"] = "appveyor"
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


@pytest.mark.legacy_travis
def test_py_matrix_travis(py_recipe, jinja_env):
    py_recipe.config["provider"]["osx"] = "travis"

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


@pytest.mark.legacy_circle
def test_py_matrix_on_circle(py_recipe, jinja_env):
    py_recipe.config["provider"]["linux"] = "circle"

    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    # this configuration should be run
    assert py_recipe.config["circle"]["enabled"]
    matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_py_matrix_on_azure(py_recipe, jinja_env):
    cnfgr_fdstk.render_azure(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    # this configuration should be run
    assert py_recipe.config["azure"]["enabled"]
    matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 8


def test_upload_on_branch_azure(upload_on_branch_recipe, jinja_env):
    cnfgr_fdstk.render_azure(
        jinja_env=jinja_env,
        forge_config=upload_on_branch_recipe.config,
        forge_dir=upload_on_branch_recipe.recipe,
    )
    # Check that the parameter is in the configuration.
    assert "upload_on_branch" in upload_on_branch_recipe.config
    assert upload_on_branch_recipe.config["upload_on_branch"] == "foo-branch"
    # Check that the parameter is in the generated file.
    with open(
        os.path.join(
            upload_on_branch_recipe.recipe,
            ".azure-pipelines",
            "azure-pipelines-osx.yml",
        )
    ) as fp:
        content_osx = yaml.load(fp)
    assert (
        'UPLOAD_ON_BRANCH="foo-branch"'
        in content_osx["jobs"][0]["steps"][-1]["script"]
    )
    assert (
        "BUILD_SOURCEBRANCHNAME"
        in content_osx["jobs"][0]["steps"][-1]["script"]
    )

    with open(
        os.path.join(
            upload_on_branch_recipe.recipe,
            ".azure-pipelines",
            "azure-pipelines-win.yml",
        )
    ) as fp:
        content_win = yaml.load(fp)
    assert (
        "UPLOAD_ON_BRANCH=foo-branch"
        in content_win["jobs"][0]["steps"][-1]["script"]
    )
    assert (
        "BUILD_SOURCEBRANCHNAME"
        in content_win["jobs"][0]["steps"][-1]["script"]
    )

    with open(
        os.path.join(
            upload_on_branch_recipe.recipe,
            ".azure-pipelines",
            "azure-pipelines-linux.yml",
        )
    ) as fp:
        content_lin = yaml.load(fp)
    assert (
        'UPLOAD_ON_BRANCH="foo-branch"'
        in content_lin["jobs"][0]["steps"][1]["script"]
    )
    assert (
        "BUILD_SOURCEBRANCHNAME"
        in content_lin["jobs"][0]["steps"][1]["script"]
    )


def test_upload_on_branch_appveyor(upload_on_branch_recipe, jinja_env):
    upload_on_branch_recipe.config["provider"]["win"] = "appveyor"
    cnfgr_fdstk.render_appveyor(
        jinja_env=jinja_env,
        forge_config=upload_on_branch_recipe.config,
        forge_dir=upload_on_branch_recipe.recipe,
    )
    # Check that the parameter is in the configuration.
    assert "upload_on_branch" in upload_on_branch_recipe.config
    assert upload_on_branch_recipe.config["upload_on_branch"] == "foo-branch"

    # Check that the parameter is in the generated file.
    with open(
        os.path.join(upload_on_branch_recipe.recipe, ".appveyor.yml")
    ) as fp:
        content = yaml.load(fp)
    assert "%APPVEYOR_REPO_BRANCH%" in content["deploy_script"][0]
    assert "UPLOAD_ON_BRANCH=foo-branch" in content["deploy_script"][1]


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


@pytest.mark.legacy_circle
def test_circle_with_empty_yum_reqs_raises(py_recipe, jinja_env):
    py_recipe.config["provider"]["linux"] = "circle"

    with open(
        os.path.join(py_recipe.recipe, "recipe", "yum_requirements.txt"), "w"
    ) as f:
        f.write("# effectively empty")
    with pytest.raises(ValueError):
        cnfgr_fdstk.render_circle(
            jinja_env=jinja_env,
            forge_config=py_recipe.config,
            forge_dir=py_recipe.recipe,
        )


def test_azure_with_empty_yum_reqs_raises(py_recipe, jinja_env):
    with open(
        os.path.join(py_recipe.recipe, "recipe", "yum_requirements.txt"), "w"
    ) as f:
        f.write("# effectively empty")
    with pytest.raises(ValueError):
        cnfgr_fdstk.render_azure(
            jinja_env=jinja_env,
            forge_config=py_recipe.config,
            forge_dir=py_recipe.recipe,
        )


@pytest.mark.legacy_circle
@pytest.mark.legacy_travis
def test_circle_osx(py_recipe, jinja_env):
    # Set legacy providers
    py_recipe.config["provider"]["osx"] = "travis"
    py_recipe.config["provider"]["linux"] = "circle"

    forge_dir = py_recipe.recipe
    travis_yml_file = os.path.join(forge_dir, ".travis.yml")
    circle_osx_file = os.path.join(forge_dir, ".circleci", "run_osx_build.sh")
    circle_linux_file = os.path.join(
        forge_dir, ".scripts", "run_docker_build.sh"
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
        forge_dir, ".scripts", "run_docker_build.sh"
    )
    circle_config_file = os.path.join(forge_dir, ".circleci", "config.yml")

    config = copy.deepcopy(linux_skipped_recipe.config)
    cnfgr_fdstk.copy_feedstock_content(config, forge_dir)
    cnfgr_fdstk.render_circle(
        jinja_env=jinja_env,
        forge_config=linux_skipped_recipe.config,
        forge_dir=forge_dir,
    )
    assert not os.path.exists(circle_osx_file)
    assert not os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)

    config["provider"]["osx"] = "circle"

    cnfgr_fdstk.copy_feedstock_content(config, forge_dir)
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
    config["provider"]["win"] = "appveyor"
    config["exclusive_config_file"] = os.path.join(
        python_skipped_recipe.recipe, "recipe", "long_config.yaml"
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


def test_migrator_recipe(recipe_migration_cfep9, jinja_env):
    cnfgr_fdstk.render_azure(
        jinja_env=jinja_env,
        forge_config=recipe_migration_cfep9.config,
        forge_dir=recipe_migration_cfep9.recipe,
    )

    with open(
        os.path.join(
            recipe_migration_cfep9.recipe,
            ".ci_support",
            "linux_python2.7.yaml",
        )
    ) as fo:
        variant = yaml.safe_load(fo)
        assert variant["zlib"] == ["1000"]


def test_migrator_downgrade_recipe(
    recipe_migration_cfep9_downgrade, jinja_env
):
    """
    Assert that even when we have two migrations targeting the same file the correct one wins.
    """
    cnfgr_fdstk.render_azure(
        jinja_env=jinja_env,
        forge_config=recipe_migration_cfep9_downgrade.config,
        forge_dir=recipe_migration_cfep9_downgrade.recipe,
    )
    assert (
        len(
            os.listdir(
                os.path.join(
                    recipe_migration_cfep9_downgrade.recipe,
                    ".ci_support",
                    "migrations",
                )
            )
        )
        == 2
    )

    with open(
        os.path.join(
            recipe_migration_cfep9_downgrade.recipe,
            ".ci_support",
            "linux_python2.7.yaml",
        )
    ) as fo:
        variant = yaml.safe_load(fo)
        assert variant["zlib"] == ["1000"]


def test_migrator_compiler_version_recipe(
    recipe_migration_win_compiled, jinja_env
):
    """
    Assert that even when we have two migrations targeting the same file the correct one wins.
    """
    cnfgr_fdstk.render_azure(
        jinja_env=jinja_env,
        forge_config=recipe_migration_win_compiled.config,
        forge_dir=recipe_migration_win_compiled.recipe,
    )
    assert (
        len(
            os.listdir(
                os.path.join(
                    recipe_migration_win_compiled.recipe,
                    ".ci_support",
                    "migrations",
                )
            )
        )
        == 1
    )

    rendered_variants = os.listdir(
        os.path.join(recipe_migration_win_compiled.recipe, ".ci_support")
    )

    assert (
        "win_c_compilervs2008python2.7target_platformwin-32.yaml"
        in rendered_variants
    )
    assert (
        "win_c_compilervs2008python2.7target_platformwin-64.yaml"
        in rendered_variants
    )
    assert (
        "win_c_compilervs2017python3.5target_platformwin-32.yaml"
        in rendered_variants
    )
    assert (
        "win_c_compilervs2017python3.5target_platformwin-64.yaml"
        in rendered_variants
    )


def test_files_skip_render(render_skipped_recipe, jinja_env):
    cnfgr_fdstk.render_README(
        jinja_env=jinja_env,
        forge_config=render_skipped_recipe.config,
        forge_dir=render_skipped_recipe.recipe,
    )
    cnfgr_fdstk.copy_feedstock_content(
        render_skipped_recipe.config, render_skipped_recipe.recipe
    )
    skipped_files = [
        ".gitignore",
        ".gitattributes",
        "README.md",
        "LICENSE.txt",
    ]
    for f in skipped_files:
        fpath = os.path.join(render_skipped_recipe.recipe, f)
        assert not os.path.exists(fpath)


def test_automerge_action(py_recipe, jinja_env):
    cnfgr_fdstk.render_actions(jinja_env=jinja_env, forge_config=atuomerge_recipe.config,forge_dir=automerge_recipe.recipe)
    cnfgr_fdstk.copy_feedstock_content(
        automerge_recipe.config, automerge_recipe.recipe
    )
    assert os.path.exists(os.path.join(automerge_recipe.recipe, '.github/workflows/main.yml'))
