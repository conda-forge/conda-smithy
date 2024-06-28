import copy
import logging
import os
import re
import shutil
import textwrap
from pathlib import Path

import pytest
import yaml

from conda_smithy import configure_feedstock


def test_noarch_skips_appveyor(noarch_recipe, jinja_env):
    noarch_recipe.config["provider"]["win"] = "appveyor"
    configure_feedstock.render_appveyor(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    # this configuration should be skipped
    assert not noarch_recipe.config["appveyor"]["enabled"]
    assert not os.path.isdir(os.path.join(noarch_recipe.recipe, ".ci_support"))


def test_noarch_skips_travis(noarch_recipe, jinja_env):
    configure_feedstock.render_travis(
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

    configure_feedstock.render_circle(
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


@pytest.mark.parametrize("recipe_dirname", ["recipe", "custom_recipe_dir"])
def test_noarch_runs_on_azure(noarch_recipe, jinja_env):
    configure_feedstock.render_azure(
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
    configure_feedstock.render_appveyor(
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

    configure_feedstock.render_travis(
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

    configure_feedstock.render_circle(
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
    configure_feedstock.render_azure(
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
    configure_feedstock.render_appveyor(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    # this configuration should be skipped
    assert py_recipe.config["appveyor"]["enabled"]
    matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # 2 python versions. Recipe uses c_compiler, but this is a zipped key
    #     and shouldn't add extra configurations
    assert len(os.listdir(matrix_dir)) == 2


@pytest.mark.legacy_travis
def test_py_matrix_travis(py_recipe, jinja_env):
    py_recipe.config["provider"]["osx"] = "travis"

    configure_feedstock.render_travis(
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

    configure_feedstock.render_circle(
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


def test_py_matrix_on_github(py_recipe, jinja_env):
    py_recipe.config["provider"]["linux"] = "github_actions"

    configure_feedstock.render_github_actions(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    # this configuration should be run
    assert py_recipe.config["github_actions"]["enabled"]
    matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2
    assert os.path.exists(
        os.path.join(
            py_recipe.recipe, ".github", "workflows", "conda-build.yml"
        )
    )


def test_py_matrix_on_azure(py_recipe, jinja_env):
    configure_feedstock.render_azure(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    # this configuration should be run
    assert py_recipe.config["azure"]["enabled"]
    matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 6


def test_stdlib_on_azure(stdlib_recipe, jinja_env):
    configure_feedstock.render_azure(
        jinja_env=jinja_env,
        forge_config=stdlib_recipe.config,
        forge_dir=stdlib_recipe.recipe,
    )
    # this configuration should be run
    assert stdlib_recipe.config["azure"]["enabled"]
    matrix_dir = os.path.join(stdlib_recipe.recipe, ".ci_support")
    assert os.path.isdir(matrix_dir)
    # find stdlib-config in generated yaml files (plus version, on unix)
    with open(os.path.join(matrix_dir, "linux_64_.yaml")) as f:
        linux_lines = f.readlines()
        linux_content = "".join(linux_lines)
    # multiline pattern to ensure we don't match other stuff accidentally
    assert re.match(r"(?s).*c_stdlib:\s*- sysroot", linux_content)
    assert re.match(r"(?s).*c_stdlib_version:\s*- ['\"]?2\.\d+", linux_content)
    with open(os.path.join(matrix_dir, "osx_64_.yaml")) as f:
        osx_lines = f.readlines()
        osx_content = "".join(osx_lines)
    assert re.match(
        r"(?s).*c_stdlib:\s*- macosx_deployment_target", osx_content
    )
    assert re.match(r"(?s).*c_stdlib_version:\s*- ['\"]?10\.9", osx_content)
    # ensure MACOSX_DEPLOYMENT_TARGET _also_ gets set to the same value
    assert re.match(
        r"(?s).*MACOSX_DEPLOYMENT_TARGET:\s*- ['\"]?10\.9", osx_content
    )
    with open(os.path.join(matrix_dir, "win_64_.yaml")) as f:
        win_lines = f.readlines()
        win_content = "".join(win_lines)
    assert re.match(r"(?s).*c_stdlib:\s*- vs", win_content)
    # no stdlib-version expected on windows


def test_stdlib_deployment_target(
    stdlib_deployment_target_recipe, jinja_env, caplog
):
    with caplog.at_level(logging.WARNING):
        configure_feedstock.render_azure(
            jinja_env=jinja_env,
            forge_config=stdlib_deployment_target_recipe.config,
            forge_dir=stdlib_deployment_target_recipe.recipe,
        )
    # this configuration should be run
    assert stdlib_deployment_target_recipe.config["azure"]["enabled"]
    matrix_dir = os.path.join(
        stdlib_deployment_target_recipe.recipe, ".ci_support"
    )
    assert os.path.isdir(matrix_dir)
    with open(os.path.join(matrix_dir, "osx_64_.yaml")) as f:
        lines = f.readlines()
        content = "".join(lines)
    # ensure both MACOSX_DEPLOYMENT_TARGET and c_stdlib_version match
    # the maximum of either, c.f. stdlib_deployment_target_recipe fixture
    assert re.match(r"(?s).*c_stdlib_version:\s*- ['\"]?10\.14", content)
    assert re.match(
        r"(?s).*MACOSX_DEPLOYMENT_TARGET:\s*- ['\"]?10\.14", content
    )
    # MACOSX_SDK_VERSION gets updated as well if it's below the other two
    assert re.match(r"(?s).*MACOSX_SDK_VERSION:\s*- ['\"]?10\.14", content)


def test_upload_on_branch_azure(upload_on_branch_recipe, jinja_env):
    configure_feedstock.render_azure(
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
        content_osx = yaml.safe_load(fp)
    assert (
        'UPLOAD_ON_BRANCH="foo-branch"'
        in content_osx["jobs"][0]["steps"][0]["script"]
    )
    assert (
        "BUILD_SOURCEBRANCHNAME"
        in content_osx["jobs"][0]["steps"][0]["script"]
    )

    with open(
        os.path.join(
            upload_on_branch_recipe.recipe,
            ".azure-pipelines",
            "azure-pipelines-win.yml",
        )
    ) as fp:
        content_win = yaml.safe_load(fp)
    win_build_step = next(
        step
        for step in content_win["jobs"][0]["steps"]
        if step["displayName"] == "Run Windows build"
    )
    assert win_build_step["env"]["UPLOAD_ON_BRANCH"] == "foo-branch"
    with open(
        os.path.join(
            upload_on_branch_recipe.recipe,
            ".scripts",
            "run_win_build.bat",
        )
    ) as fp:
        build_script_win = fp.read()
    assert "BUILD_SOURCEBRANCHNAME" in build_script_win

    with open(
        os.path.join(
            upload_on_branch_recipe.recipe,
            ".azure-pipelines",
            "azure-pipelines-linux.yml",
        )
    ) as fp:
        content_lin = yaml.safe_load(fp)
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
    configure_feedstock.render_appveyor(
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
        content = yaml.safe_load(fp)
    assert "%APPVEYOR_REPO_BRANCH%" in content["deploy_script"][0]
    assert "UPLOAD_ON_BRANCH=foo-branch" in content["deploy_script"][-2]


def test_circle_with_yum_reqs(py_recipe, jinja_env):
    with open(
        os.path.join(py_recipe.recipe, "recipe", "yum_requirements.txt"), "w"
    ) as f:
        f.write("nano\n")
    configure_feedstock.render_circle(
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
        configure_feedstock.render_circle(
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
        configure_feedstock.render_azure(
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
    circle_osx_file = os.path.join(forge_dir, ".scripts", "run_osx_build.sh")
    circle_linux_file = os.path.join(
        forge_dir, ".scripts", "run_docker_build.sh"
    )
    circle_config_file = os.path.join(forge_dir, ".circleci", "config.yml")

    configure_feedstock.clear_scripts(forge_dir)
    configure_feedstock.render_circle(
        jinja_env=jinja_env, forge_config=py_recipe.config, forge_dir=forge_dir
    )
    assert not os.path.exists(circle_osx_file)
    assert os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)
    configure_feedstock.render_travis(
        jinja_env=jinja_env, forge_config=py_recipe.config, forge_dir=forge_dir
    )
    assert os.path.exists(travis_yml_file)

    configure_feedstock.clear_scripts(forge_dir)
    config = copy.deepcopy(py_recipe.config)
    config["provider"]["osx"] = "circle"
    configure_feedstock.render_circle(
        jinja_env=jinja_env, forge_config=config, forge_dir=forge_dir
    )
    assert os.path.exists(circle_osx_file)
    assert os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)
    configure_feedstock.render_travis(
        jinja_env=jinja_env, forge_config=config, forge_dir=forge_dir
    )
    assert not os.path.exists(travis_yml_file)

    configure_feedstock.clear_scripts(forge_dir)
    config = copy.deepcopy(py_recipe.config)
    config["provider"]["linux"] = "dummy"
    config["provider"]["osx"] = "circle"
    configure_feedstock.render_circle(
        jinja_env=jinja_env, forge_config=config, forge_dir=forge_dir
    )
    assert os.path.exists(circle_osx_file)
    assert not os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)


def test_circle_skipped(linux_skipped_recipe, jinja_env):
    forge_dir = linux_skipped_recipe.recipe
    circle_osx_file = os.path.join(forge_dir, ".scripts", "run_osx_build.sh")
    circle_linux_file = os.path.join(
        forge_dir, ".scripts", "run_docker_build.sh"
    )
    circle_config_file = os.path.join(forge_dir, ".circleci", "config.yml")

    config = copy.deepcopy(linux_skipped_recipe.config)
    configure_feedstock.copy_feedstock_content(config, forge_dir)
    configure_feedstock.render_circle(
        jinja_env=jinja_env,
        forge_config=linux_skipped_recipe.config,
        forge_dir=forge_dir,
    )
    assert not os.path.exists(circle_osx_file)
    assert not os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)

    config["provider"]["osx"] = "circle"

    configure_feedstock.copy_feedstock_content(config, forge_dir)
    configure_feedstock.render_circle(
        jinja_env=jinja_env, forge_config=config, forge_dir=forge_dir
    )
    assert os.path.exists(circle_osx_file)
    assert not os.path.exists(circle_linux_file)
    assert os.path.exists(circle_config_file)


def test_render_with_all_skipped_generates_readme(skipped_recipe, jinja_env):
    configure_feedstock.render_readme(
        jinja_env=jinja_env,
        forge_config=skipped_recipe.config,
        forge_dir=skipped_recipe.recipe,
    )
    readme_path = os.path.join(skipped_recipe.recipe, "README.md")
    assert os.path.exists(readme_path)
    with open(readme_path, "rb") as readme_file:
        content = readme_file.read()
    assert b"skip-test-meta" in content


def test_render_windows_with_skipped_python(python_skipped_recipe, jinja_env):
    config = python_skipped_recipe.config
    config["provider"]["win"] = "appveyor"
    config["exclusive_config_file"] = os.path.join(
        python_skipped_recipe.recipe, "recipe", "long_config.yaml"
    )
    configure_feedstock.render_appveyor(
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
    configure_feedstock.render_readme(
        jinja_env=jinja_env,
        forge_config=noarch_recipe.config,
        forge_dir=noarch_recipe.recipe,
    )
    readme_path = os.path.join(noarch_recipe.recipe, "README.md")
    assert os.path.exists(readme_path)
    with open(readme_path, "rb") as readme_file:
        readme_file.seek(-1, os.SEEK_END)
        assert readme_file.read() == b"\n"


def test_secrets(py_recipe, jinja_env):
    configure_feedstock.render_azure(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )

    run_docker_build = os.path.join(
        py_recipe.recipe, ".scripts", "run_docker_build.sh"
    )
    with open(run_docker_build, "rb") as run_docker_build_file:
        content = run_docker_build_file.read()
    assert b"-e BINSTAR_TOKEN" in content

    for config_yaml in os.listdir(
        os.path.join(py_recipe.recipe, ".azure-pipelines")
    ):
        if config_yaml.endswith(".yaml"):
            with open(config_yaml) as fo:
                config = yaml.safe_load(fo)
                if "jobs" in config:
                    assert any(
                        any(
                            step.get("env", {}).get("BINSTAR_TOKEN", None)
                            == "$(BINSTAR_TOKEN)"
                            for step in job["steps"]
                        )
                        for job in config["jobs"]
                    )

    py_recipe.config["provider"]["linux_aarch64"] = "drone"
    configure_feedstock.render_drone(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )

    with open(os.path.join(py_recipe.recipe, ".drone.yml")) as fo:
        config = list(yaml.safe_load_all(fo))[-1]
        assert any(
            step.get("environment", {})
            .get("BINSTAR_TOKEN", {})
            .get("from_secret", None)
            == "BINSTAR_TOKEN"
            for step in config["steps"]
        )


def test_migrator_recipe(recipe_migration_cfep9, jinja_env):
    configure_feedstock.render_azure(
        jinja_env=jinja_env,
        forge_config=recipe_migration_cfep9.config,
        forge_dir=recipe_migration_cfep9.recipe,
    )

    with open(
        os.path.join(
            recipe_migration_cfep9.recipe,
            ".ci_support",
            "linux_64_python2.7.yaml",
        )
    ) as fo:
        variant = yaml.safe_load(fo)
        assert variant["zlib"] == ["1000"]


def test_migrator_cfp_override(recipe_migration_cfep9, jinja_env):
    cfp_file = recipe_migration_cfep9.config["exclusive_config_file"]
    cfp_migration_dir = os.path.join(
        os.path.dirname(cfp_file), "share", "conda-forge", "migrations"
    )
    os.makedirs(cfp_migration_dir, exist_ok=True)
    with open(os.path.join(cfp_migration_dir, "zlib2.yaml"), "w") as f:
        f.write(
            textwrap.dedent(
                """
                migrator_ts: 1
                zlib:
                   - 1001
                """
            )
        )
    configure_feedstock.render_azure(
        jinja_env=jinja_env,
        forge_config=recipe_migration_cfep9.config,
        forge_dir=recipe_migration_cfep9.recipe,
    )

    with open(
        os.path.join(
            recipe_migration_cfep9.recipe,
            ".ci_support",
            "linux_64_python2.7.yaml",
        )
    ) as fo:
        variant = yaml.safe_load(fo)
        assert variant["zlib"] == ["1001"]


def test_migrator_delete_old(recipe_migration_cfep9, jinja_env):
    cfp_file = recipe_migration_cfep9.config["exclusive_config_file"]
    cfp_migration_dir = os.path.join(
        os.path.dirname(cfp_file), "share", "conda-forge", "migrations"
    )
    assert os.path.exists(
        os.path.join(
            recipe_migration_cfep9.recipe,
            ".ci_support",
            "migrations",
            "zlib.yaml",
        )
    )
    os.makedirs(cfp_migration_dir, exist_ok=True)
    configure_feedstock.render_azure(
        jinja_env=jinja_env,
        forge_config=recipe_migration_cfep9.config,
        forge_dir=recipe_migration_cfep9.recipe,
    )
    assert not os.path.exists(
        os.path.join(
            recipe_migration_cfep9.recipe,
            ".ci_support",
            "migrations",
            "zlib.yaml",
        )
    )


def test_migrator_downgrade_recipe(
    recipe_migration_cfep9_downgrade, jinja_env
):
    """
    Assert that even when we have two migrations targeting the same file the correct one wins.
    """
    configure_feedstock.render_azure(
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
            "linux_64_python2.7.yaml",
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
    configure_feedstock.render_azure(
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

    assert "win_64_c_compilervs2008python2.7.yaml" in rendered_variants
    assert "win_64_c_compilervs2017python3.5.yaml" in rendered_variants


def test_files_skip_render(render_skipped_recipe, jinja_env):
    configure_feedstock.render_readme(
        jinja_env=jinja_env,
        forge_config=render_skipped_recipe.config,
        forge_dir=render_skipped_recipe.recipe,
    )
    configure_feedstock.copy_feedstock_content(
        render_skipped_recipe.config, render_skipped_recipe.recipe
    )
    skipped_files = [
        ".gitignore",
        ".gitattributes",
        "README.md",
        "LICENSE.txt",
        ".github/workflows/webservices.yml",
    ]
    for f in skipped_files:
        fpath = os.path.join(render_skipped_recipe.recipe, f)
        assert not os.path.exists(fpath)


def test_choco_install(choco_recipe, jinja_env):
    configure_feedstock.render_azure(
        jinja_env=jinja_env,
        forge_config=choco_recipe.config,
        forge_dir=choco_recipe.recipe,
    )
    azure_file = os.path.join(
        os.path.join(
            choco_recipe.recipe, ".azure-pipelines", "azure-pipelines-win.yml"
        )
    )
    assert os.path.isfile(azure_file)
    with open(azure_file) as f:
        contents = f.read()
    exp = """
    - script: |
        choco install pkg0 -fdv -y --debug
      displayName: "Install Chocolatey Package: pkg0"

    - script: |
        choco install pkg1 --version=X.Y.Z -fdv -y --debug
      displayName: "Install Chocolatey Package: pkg1 --version=X.Y.Z"
""".strip()
    assert exp in contents


def test_webservices_action_exists(py_recipe, jinja_env):
    configure_feedstock.render_github_actions_services(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    assert os.path.exists(
        os.path.join(py_recipe.recipe, ".github/workflows/webservices.yml")
    )
    with open(
        os.path.join(py_recipe.recipe, ".github/workflows/webservices.yml")
    ) as f:
        action_config = yaml.safe_load(f)
    assert "jobs" in action_config
    assert "webservices" in action_config["jobs"]


def test_automerge_action_exists(py_recipe, jinja_env):
    configure_feedstock.render_github_actions_services(
        jinja_env=jinja_env,
        forge_config=py_recipe.config,
        forge_dir=py_recipe.recipe,
    )
    assert os.path.exists(
        os.path.join(py_recipe.recipe, ".github/workflows/automerge.yml")
    )
    with open(
        os.path.join(py_recipe.recipe, ".github/workflows/automerge.yml")
    ) as f:
        action_config = yaml.safe_load(f)
    assert "jobs" in action_config
    assert "automerge-action" in action_config["jobs"]


def test_conda_forge_yaml_empty(config_yaml):
    load_forge_config = lambda: configure_feedstock._load_forge_config(  # noqa
        config_yaml,
        exclusive_config_file=os.path.join(
            config_yaml, "recipe", "default_config.yaml"
        ),
    )

    assert load_forge_config()["recipe_dir"] == "recipe"

    os.unlink(os.path.join(config_yaml, "conda-forge.yml"))
    with pytest.raises(RuntimeError):
        load_forge_config()

    with open(os.path.join(config_yaml, "conda-forge.yml"), "w"):
        pass
    assert load_forge_config()["recipe_dir"] == "recipe"


def test_noarch_platforms_bad_yaml(config_yaml, caplog):
    load_forge_config = lambda: configure_feedstock._load_forge_config(  # noqa
        config_yaml,
        exclusive_config_file=os.path.join(
            config_yaml, "recipe", "default_config.yaml"
        ),
    )

    with open(os.path.join(config_yaml, "conda-forge.yml"), "a+") as fp:
        fp.write("noarch_platforms: [eniac, zx80]")

    with caplog.at_level(logging.WARNING):
        load_forge_config()

    assert "eniac" in caplog.text


def _load_forge_config(config_yaml, forge_yml):
    # noinspection PyProtectedMember
    return configure_feedstock._load_forge_config(
        config_yaml,
        exclusive_config_file=os.path.join(
            config_yaml, "recipe", "default_config.yaml"
        ),
        forge_yml=forge_yml,
    )


def test_forge_yml_alt_path(config_yaml):
    forge_yml = os.path.join(config_yaml, "conda-forge.yml")
    forge_yml_alt = os.path.join(
        config_yaml, ".config", "feedstock-config.yml"
    )

    os.mkdir(os.path.dirname(forge_yml_alt))
    os.rename(forge_yml, forge_yml_alt)

    with pytest.raises(RuntimeError):
        _load_forge_config(config_yaml, None)

    assert (
        _load_forge_config(config_yaml, forge_yml_alt)["recipe_dir"]
        == "recipe"
    )


def test_cos7_env_render(py_recipe, jinja_env):
    forge_config = copy.deepcopy(py_recipe.config)
    forge_config["os_version"] = {"linux_64": "cos7"}
    has_env = "DEFAULT_LINUX_VERSION" in os.environ
    if has_env:
        old_val = os.environ["DEFAULT_LINUX_VERSION"]
        del os.environ["DEFAULT_LINUX_VERSION"]

    try:
        assert "DEFAULT_LINUX_VERSION" not in os.environ
        configure_feedstock.render_azure(
            jinja_env=jinja_env,
            forge_config=forge_config,
            forge_dir=py_recipe.recipe,
        )
        assert os.environ["DEFAULT_LINUX_VERSION"] == "cos7"

        # this configuration should be run
        assert forge_config["azure"]["enabled"]
        matrix_dir = os.path.join(py_recipe.recipe, ".ci_support")
        assert os.path.isdir(matrix_dir)
        # single matrix entry - readme is generated later in main function
        assert len(os.listdir(matrix_dir)) == 6

    finally:
        if has_env:
            os.environ["DEFAULT_LINUX_VERSION"] = old_val
        else:
            if "DEFAULT_LINUX_VERSION" in os.environ:
                del os.environ["DEFAULT_LINUX_VERSION"]


def test_cuda_enabled_render(cuda_enabled_recipe, jinja_env):
    forge_config = copy.deepcopy(cuda_enabled_recipe.config)
    has_env = "CF_CUDA_ENABLED" in os.environ
    if has_env:
        old_val = os.environ["CF_CUDA_ENABLED"]
        del os.environ["CF_CUDA_ENABLED"]

    try:
        assert "CF_CUDA_ENABLED" not in os.environ
        configure_feedstock.render_azure(
            jinja_env=jinja_env,
            forge_config=forge_config,
            forge_dir=cuda_enabled_recipe.recipe,
        )
        assert os.environ["CF_CUDA_ENABLED"] == "True"

        # this configuration should be run
        assert forge_config["azure"]["enabled"]
        matrix_dir = os.path.join(cuda_enabled_recipe.recipe, ".ci_support")
        assert os.path.isdir(matrix_dir)
        # single matrix entry - readme is generated later in main function
        assert len(os.listdir(matrix_dir)) == 6

    finally:
        if has_env:
            os.environ["CF_CUDA_ENABLED"] = old_val
        else:
            if "CF_CUDA_ENABLED" in os.environ:
                del os.environ["CF_CUDA_ENABLED"]


def test_conda_build_tools(config_yaml, caplog):
    load_forge_config = lambda: configure_feedstock._load_forge_config(  # noqa
        config_yaml,
        exclusive_config_file=os.path.join(
            config_yaml, "recipe", "default_config.yaml"
        ),
    )

    cfg = load_forge_config()
    assert (
        "build_with_mambabuild" not in cfg
    )  # superseded by conda_build_tool=mambabuild
    assert cfg["conda_build_tool"] == "conda-build"  # current default

    # legacy compatibility config
    with open(os.path.join(config_yaml, "conda-forge.yml")) as fp:
        unmodified = fp.read()
    with open(os.path.join(config_yaml, "conda-forge.yml"), "a+") as fp:
        fp.write("build_with_mambabuild: true")
    with pytest.deprecated_call(match="build_with_mambabuild is deprecated"):
        assert load_forge_config()["conda_build_tool"] == "mambabuild"

    with open(os.path.join(config_yaml, "conda-forge.yml"), "w") as fp:
        fp.write(unmodified)
        fp.write("build_with_mambabuild: false")

    with pytest.deprecated_call(match="build_with_mambabuild is deprecated"):
        assert load_forge_config()["conda_build_tool"] == "conda-build"

    with open(os.path.join(config_yaml, "conda-forge.yml"), "w") as fp:
        fp.write(unmodified)
        fp.write("conda_build_tool: does-not-exist")

    with caplog.at_level(logging.WARNING):
        assert load_forge_config()
    assert "does-not-exist" in caplog.text


def test_remote_ci_setup(config_yaml):
    load_forge_config = lambda: configure_feedstock._load_forge_config(  # noqa
        config_yaml,
        exclusive_config_file=os.path.join(
            config_yaml, "recipe", "default_config.yaml"
        ),
    )
    cfg = load_forge_config()
    with open(os.path.join(config_yaml, "conda-forge.yml")) as fp:
        unmodified = fp.read()

    with open(os.path.join(config_yaml, "conda-forge.yml"), "a+") as fp:
        fp.write(
            "remote_ci_setup: ['conda-forge-ci-setup=3', 'py-lief<0.12']\n"
        )
        fp.write("conda_install_tool: conda\n")
    cfg = load_forge_config()
    # pylief was quoted due to <
    assert cfg["remote_ci_setup"] == [
        "conda-forge-ci-setup=3",
        '"py-lief<0.12"',
    ]

    assert cfg["remote_ci_setup_update"] == [
        "conda-forge-ci-setup",
        "py-lief",
    ]

    with open(os.path.join(config_yaml, "conda-forge.yml"), "w") as fp:
        fp.write(unmodified + "\n")
        fp.write(
            "remote_ci_setup: ['conda-forge-ci-setup=3', 'py-lief<0.12']\n"
        )
        fp.write("conda_install_tool: mamba\n")
    cfg = load_forge_config()
    # with conda_install_tool = mamba, we don't strip constraints
    assert (
        cfg["remote_ci_setup"]
        == cfg["remote_ci_setup_update"]
        == [
            "conda-forge-ci-setup=3",
            '"py-lief<0.12"',
        ]
    )


@pytest.mark.parametrize(
    "squished_input_variants,squished_used_variants,all_used_vars,expected_used_key_values",
    [
        (
            dict(
                [
                    (
                        "extend_keys",
                        {
                            "extend_keys",
                            "ignore_build_only_deps",
                            "ignore_version",
                            "pin_run_as_build",
                        },
                    ),
                    ("ignore_build_only_deps", {"python", "numpy"}),
                    (
                        "pin_run_as_build",
                        dict(
                            [
                                (
                                    "python",
                                    {"max_pin": "x.x", "min_pin": "x.x"},
                                ),
                                (
                                    "r-base",
                                    {"max_pin": "x.x", "min_pin": "x.x"},
                                ),
                                ("flann", {"max_pin": "x.x.x"}),
                                ("graphviz", {"max_pin": "x"}),
                                ("libsvm", {"max_pin": "x"}),
                                ("netcdf-cxx4", {"max_pin": "x.x"}),
                                ("occt", {"max_pin": "x.x"}),
                                ("poppler", {"max_pin": "x.x"}),
                                ("vlfeat", {"max_pin": "x.x.x"}),
                            ]
                        ),
                    ),
                    ("glew", ["2.1"]),
                    ("pango", ["1.50"]),
                    ("libgoogle_cloud_compute_devel", ["2.21"]),
                    ("dav1d", ["1.2.1"]),
                    ("lzo", ["2"]),
                    ("pybind11_abi", ["4"]),
                    ("sqlite", ["3"]),
                    ("nlopt", ["2.7"]),
                    ("aws_checksums", ["0.1.18"]),
                    ("aws_c_mqtt", ["0.10.2"]),
                    ("aws_c_s3", ["0.5.1"]),
                    ("libaec", ["1"]),
                    ("pari", ["2.15.* *_pthread"]),
                    ("libgoogle_cloud_devel", ["2.21"]),
                    ("libjpeg_turbo", ["3"]),
                    ("libblitz", ["1.0.2"]),
                    ("ptscotch", ["7.0.4"]),
                    ("openslide", ["4"]),
                    ("libdeflate", ["1.19"]),
                    ("gf2x", ["1.3"]),
                    ("cuda_compiler_version_min", ["11.2"]),
                    ("aws_c_event_stream", ["0.4.2"]),
                    ("arb", ["2.23"]),
                    ("expat", ["2"]),
                    ("bzip2", ["1"]),
                    ("target_goexe", [""]),
                    ("VERBOSE_AT", ["V=1"]),
                    ("cran_mirror", ["https://cran.r-project.org"]),
                    ("aws_c_compression", ["0.2.18"]),
                    ("libsvm", ["332"]),
                    ("uhd", ["4.6.0"]),
                    ("libcrc32c", ["1.1"]),
                    ("libtensorflow_cc", ["2.15"]),
                    ("msgpack_cxx", ["6"]),
                    ("libunwind", ["1.6"]),
                    ("libv8", ["8.9.83"]),
                    ("libpq", ["16"]),
                    ("lmdb", ["0.9.29"]),
                    ("root_base", ["6.28.10", "6.30.2"]),
                    ("geotiff", ["1.7.1"]),
                    ("google_cloud_cpp", ["2.21"]),
                    ("mpfr", ["4"]),
                    ("gmp", ["6"]),
                    ("harfbuzz", ["8"]),
                    ("_libgcc_mutex", ["0.1 conda_forge"]),
                    ("wxwidgets", ["3.2"]),
                    ("svt_av1", ["1.8.0"]),
                    ("libcurl", ["8"]),
                    ("liblapack", ["3.9 *netlib"]),
                    ("libmatio_cpp", ["0.2.3"]),
                    ("libvips", ["8"]),
                    ("aws_sdk_cpp", ["1.11.267"]),
                    ("proj", ["9.3.1"]),
                    ("libgoogle_cloud_all_devel", ["2.21"]),
                    ("libgoogle_cloud_aiplatform_devel", ["2.21"]),
                    ("libpcap", ["1.10"]),
                    ("pulseaudio_client", ["16.1"]),
                    ("ffmpeg", ["6"]),
                    ("graphviz", ["9"]),
                    ("cudnn", ["8"]),
                    ("x264", ["1!164.*"]),
                    ("libcint", ["5.5"]),
                    ("s2n", ["1.4.4"]),
                    ("sdl2_ttf", ["2"]),
                    ("pugixml", ["1.14"]),
                    ("flatbuffers", ["23.5.26"]),
                    ("krb5", ["1.20"]),
                    ("ntl", ["11.4.3"]),
                    ("libev", ["4.33"]),
                    ("aws_c_io", ["0.14.4"]),
                    ("target_gobin", ["${PREFIX}/bin/"]),
                    ("cxx_compiler", ["gxx"]),
                    ("ccr", ["1.3"]),
                    ("postgresql", ["16"]),
                    ("antic", ["0.2"]),
                    ("gst_plugins_base", ["1.22"]),
                    ("rdma_core", ["49"]),
                    ("libssh2", ["1"]),
                    ("libtiff", ["4.6"]),
                    ("kealib", ["1.5"]),
                    ("mpich", ["4"]),
                    ("spdlog", ["1.12"]),
                    ("netcdf_fortran", ["4.6"]),
                    ("elfutils", ["0.190"]),
                    ("gsl", ["2.7"]),
                    ("eclib", ["20231211"]),
                    ("tiledb", ["2.20"]),
                    ("libhugetlbfs", ["2"]),
                    ("nss", ["3"]),
                    ("netcdf_cxx4", ["4.3"]),
                    ("pcl", ["1.13.1"]),
                    ("sox", ["14.4.2"]),
                    ("superlu_dist", ["8"]),
                    ("libgoogle_cloud_dialogflow_es_devel", ["2.21"]),
                    ("attr", ["2.5"]),
                    ("log4cxx", ["1.2.0"]),
                    ("aws_c_sdkutils", ["0.1.15"]),
                    ("libxml2", ["2"]),
                    ("libsentencepiece", ["0.1.99"]),
                    ("tbb_devel", ["2021"]),
                    ("jsoncpp", ["1.9.5"]),
                    ("msgpack_c", ["6"]),
                    ("libzip", ["1"]),
                    ("mkl", ["2023"]),
                    ("giflib", ["5.2"]),
                    ("fortran_compiler", ["gfortran"]),
                    ("libboost_python_devel", ["1.82"]),
                    ("dbus", ["1"]),
                    ("libwebp_base", ["1"]),
                    ("libflint", ["2.9"]),
                    ("libsoup", ["3"]),
                    ("libgoogle_cloud_bigtable_devel", ["2.21"]),
                    ("abseil_cpp", ["20220623.0"]),
                    ("librdkafka", ["2.2"]),
                    ("starlink_ast", ["9.2.7"]),
                    ("lerc", ["4"]),
                    ("davix", ["0.8"]),
                    ("libxsmm", ["1"]),
                    ("poppler", ["23.07"]),
                    ("dcap", ["2.47"]),
                    ("gnuradio_core", ["3.10.9"]),
                    ("gsoap", ["2.8.123"]),
                    ("fmt", ["10"]),
                    ("libopencv", ["4.9.0"]),
                    ("aws_c_http", ["0.8.1"]),
                    ("lua", ["5"]),
                    ("qt", ["5.15"]),
                    ("pcre", ["8"]),
                    ("ldas_tools_framecpp", ["2.9"]),
                    ("ruby", ["2.5", "2.6"]),
                    ("libgoogle_cloud_policytroubleshooter_devel", ["2.21"]),
                    ("libdap4", ["3.20.6"]),
                    ("mimalloc", ["2.1.2"]),
                    ("coin_or_osi", ["0.108"]),
                    ("gdk_pixbuf", ["2"]),
                    ("target_goarch", ["amd64"]),
                    ("assimp", ["5.3.1"]),
                    ("flann", ["1.9.2"]),
                    ("gct", ["6.2.1629922860"]),
                    ("aws_c_auth", ["0.7.16"]),
                    ("pyqtchart", ["5.15"]),
                    ("coin_or_clp", ["1.17"]),
                    ("grpc_cpp", ["1.52"]),
                    ("libgdal", ["3.8"]),
                    ("volk", ["3.1"]),
                    ("curl", ["8"]),
                    ("geos", ["3.12.1"]),
                    ("zstd", ["1.5"]),
                    ("libabseil", ["20240116"]),
                    ("blas_impl", ["openblas", "mkl", "blis"]),
                    ("openblas", ["0.3.*"]),
                    ("zlib_ng", ["2.0"]),
                    ("liblapacke", ["3.9 *netlib"]),
                    ("libframel", ["8.41"]),
                    ("postgresql_plpython", ["16"]),
                    ("libgoogle_cloud", ["2.21"]),
                    ("gstreamer", ["1.22"]),
                    ("lcms", ["2"]),
                    ("libuuid", ["2"]),
                    ("coin_or_cgl", ["0.60"]),
                    ("rust_compiler", ["rust"]),
                    ("bullet_cpp", ["3.25"]),
                    ("fftw", ["3"]),
                    ("tbb", ["2021"]),
                    ("libsecret", ["0.18"]),
                    ("libgoogle_cloud_spanner_devel", ["2.21"]),
                    ("channel_sources", ["conda-forge"]),
                    ("pcre2", ["10.42"]),
                    ("glib", ["2"]),
                    ("google_cloud_cpp_common", ["0.25.0"]),
                    ("openmpi", ["4"]),
                    ("ncurses", ["6"]),
                    ("openh264", ["2.4.1"]),
                    ("wcslib", ["8"]),
                    ("soapysdr", ["0.8"]),
                    ("tinyxml2", ["10"]),
                    ("libavif", ["1.0.1"]),
                    ("cairo", ["1"]),
                    ("icu", ["73"]),
                    ("libsndfile", ["1.2"]),
                    ("aom", ["3.7"]),
                    ("x265", ["3.5"]),
                    ("jasper", ["4"]),
                    ("pyqt", ["5.15"]),
                    ("xrootd", ["5"]),
                    ("gnutls", ["3.7"]),
                    ("rocksdb", ["8.0"]),
                    ("libgit2", ["1.7"]),
                    ("libgoogle_cloud_oauth2_devel", ["2.21"]),
                    ("zfp", ["1.0"]),
                    ("libtorch", ["2.1"]),
                    ("libarchive", ["3.7"]),
                    ("freetype", ["2"]),
                    ("poco", ["1.13.2"]),
                    ("libthrift", ["0.19.0"]),
                    ("qt_main", ["5.15"]),
                    ("libosqp", ["0.6.3"]),
                    ("ucx", ["1.15.0"]),
                    ("libgoogle_cloud_automl_devel", ["2.21"]),
                    ("slepc", ["3.20"]),
                    ("aws_c_cal", ["0.6.10"]),
                    ("p11_kit", ["0.24"]),
                    ("target_platform", ["linux-64"]),
                    ("libblas", ["3.9 *netlib"]),
                    ("libgoogle_cloud_bigquery_devel", ["2.21"]),
                    ("libmicrohttpd", ["1.0"]),
                    ("mpg123", ["1.32"]),
                    ("srm_ifce", ["1.24.6"]),
                    ("petsc", ["3.20"]),
                    ("libiconv", ["1"]),
                    ("aws_crt_cpp", ["0.26.2"]),
                    ("console_bridge", ["1.0"]),
                    ("libgoogle_cloud_storage_devel", ["2.21"]),
                    ("lz4_c", ["1.9.3"]),
                    ("mumps_mpi", ["5.6.2"]),
                    ("coincbc", ["2.10"]),
                    ("orc", ["1.9.2"]),
                    ("libcblas", ["3.9 *netlib"]),
                    ("readline", ["8"]),
                    ("nodejs", ["18", "20"]),
                    ("glpk", ["5.0"]),
                    ("imath", ["3.1.9"]),
                    ("gdal", ["3.8"]),
                    ("nettle", ["3.9"]),
                    ("qtkeychain", ["0.14"]),
                    ("c_ares", ["1"]),
                    ("libduckdb_devel", ["0.9.2"]),
                    ("occt", ["7.7.2"]),
                    ("qt6_main", ["6.6"]),
                    ("perl", ["5.32.1"]),
                    ("libidn2", ["2"]),
                    ("pyqtwebengine", ["5.15"]),
                    ("coin_or_utils", ["2.11"]),
                    ("libopenvino_dev", ["2023.3.0"]),
                    ("googleapis_cpp", ["0.10"]),
                    ("libwebp", ["1"]),
                    ("coin_or_cbc", ["2.10"]),
                    ("channel_targets", ["conda-forge main"]),
                    ("sdl2_image", ["2"]),
                    ("sdl2_mixer", ["2"]),
                    ("vtk", ["9.2.6"]),
                    ("librsvg", ["2"]),
                    ("jpeg", ["9"]),
                    ("hdf4", ["4.2.15"]),
                    ("pytorch", ["2.1"]),
                    ("libintervalxt", ["3"]),
                    ("thrift_cpp", ["0.19.0"]),
                    ("libgoogle_cloud_discoveryengine_devel", ["2.21"]),
                    ("arpack", ["3.8"]),
                    ("libtensorflow", ["2.15"]),
                    ("vlfeat", ["0.9.21"]),
                    ("snappy", ["1"]),
                    ("capnproto", ["0.10.2"]),
                    ("libmatio", ["1.5.26"]),
                    ("c_compiler", ["gcc"]),
                    ("cgo_compiler", ["go-cgo"]),
                    ("ipopt", ["3.14.14"]),
                    ("libiio", ["0"]),
                    ("singular", ["4.3.2.p8"]),
                    ("libhwy", ["1.0"]),
                    ("zeromq", ["4.3.5"]),
                    ("pixman", ["0"]),
                    ("libspatialindex", ["1.9.3"]),
                    ("libffi", ["3.4"]),
                    ("nspr", ["4"]),
                    ("petsc4py", ["3.20"]),
                    ("libsqlite", ["3"]),
                    ("pulseaudio", ["16.1"]),
                    ("libopentelemetry_cpp", ["1.14"]),
                    ("libptscotch", ["7.0.4"]),
                    ("libraw", ["0.21"]),
                    ("libgoogle_cloud_dlp_devel", ["2.21"]),
                    ("libgoogle_cloud_iam_devel", ["2.21"]),
                    ("openjpeg", ["2"]),
                    ("libhwloc", ["2.9.1"]),
                    ("r_base", ["4.2", "4.3"]),
                    ("gfal2", ["2.21"]),
                    ("libexactreal", ["4"]),
                    ("mkl_devel", ["2023"]),
                    ("zlib", ["1.2"]),
                    ("libmed", ["4.1"]),
                    ("fontconfig", ["2"]),
                    ("xz", ["5"]),
                    ("suitesparse", ["5"]),
                    ("libgoogle_cloud_speech_devel", ["2.21"]),
                    ("sdl2_net", ["2"]),
                    ("slepc4py", ["3.20"]),
                    ("tk", ["8.6"]),
                    ("libpng", ["1.6"]),
                    ("libssh", ["0.10"]),
                    ("urdfdom", ["3.1"]),
                    ("metis", ["5.1.0"]),
                    ("libnetcdf", ["4.9.2"]),
                    ("sdl2", ["2"]),
                    ("target_goos", ["linux"]),
                    ("cfitsio", ["4.3.0"]),
                    ("pulseaudio_daemon", ["16.1"]),
                    ("mumps_seq", ["5.6.2"]),
                    ("hdf5", ["1.14.3"]),
                    ("nccl", ["2"]),
                    ("libevent", ["2.1.12"]),
                    ("exiv2", ["0.27"]),
                    ("libeantic", ["2"]),
                    ("alsa_lib", ["1.2.10"]),
                    ("glog", ["0.7"]),
                    ("libscotch", ["7.0.4"]),
                    ("cutensor", ["2"]),
                    ("json_c", ["0.17"]),
                    ("aws_c_common", ["0.9.13"]),
                    ("isl", ["0.26"]),
                    ("openssl", ["3"]),
                    ("xerces_c", ["3.2"]),
                    ("cpu_optimization_target", ["nocona"]),
                    ("libflatsurf", ["3"]),
                    ("libkml", ["1.3"]),
                    ("gflags", ["2.2"]),
                    ("libboost_devel", ["1.82"]),
                    ("libgoogle_cloud_dialogflow_cx_devel", ["2.21"]),
                    ("VERBOSE_CM", ["VERBOSE=1"]),
                    ("openexr", ["3.2"]),
                    ("scotch", ["7.0.4"]),
                    ("libgoogle_cloud_pubsub_devel", ["2.21"]),
                    ("libabseil_static", ["20220623.0"]),
                    ("go_compiler", ["go-nocgo"]),
                    ("re2", ["2023.06.02"]),
                    ("tensorflow", ["2.15"]),
                    ("libarrow_all", ("12", "14", "13", "15")),
                    ("arrow_cpp", ("12", "14", "13", "15")),
                    ("libarrow", ("12", "14", "13", "15")),
                    ("c_compiler_version", ("12", "11", "10", "12")),
                    ("fortran_compiler_version", ("12", "11", "10", "12")),
                    ("cdt_name", ("cos7", "cos7", "cos7", "cos6")),
                    (
                        "docker_image",
                        (
                            "quay.io/condaforge/linux-anvil-cos7-x86_64",
                            "quay.io/condaforge/linux-anvil-cuda:11.8",
                            "quay.io/condaforge/linux-anvil-cuda:11.2",
                            "quay.io/condaforge/linux-anvil-cos7-x86_64",
                        ),
                    ),
                    ("cuda_compiler", ("cuda-nvcc", "nvcc", "nvcc", "None")),
                    ("cxx_compiler_version", ("12", "11", "10", "12")),
                    (
                        "cuda_compiler_version",
                        ("12.0", "11.8", "11.2", "None"),
                    ),
                    ("libgrpc", ("1.61",)),
                    ("libprotobuf", ("4.25.2",)),
                    ("c_stdlib_version", ("2.12",)),
                    ("c_stdlib", ("sysroot",)),
                    (
                        "python",
                        (
                            "3.9.* *_cpython",
                            "3.10.* *_cpython",
                            "3.11.* *_cpython",
                            "3.8.* *_cpython",
                            "3.12.* *_cpython",
                        ),
                    ),
                    ("numpy", ("1.22", "1.22", "1.23", "1.22", "1.26")),
                    (
                        "python_impl",
                        (
                            "cpython",
                            "cpython",
                            "cpython",
                            "cpython",
                            "cpython",
                        ),
                    ),
                    (
                        "zip_keys",
                        [
                            ["python", "numpy", "python_impl"],
                            ["arrow_cpp", "libarrow", "libarrow_all"],
                            ["c_stdlib", "c_stdlib_version"],
                            [
                                "c_compiler_version",
                                "cxx_compiler_version",
                                "fortran_compiler_version",
                                "cuda_compiler",
                                "cuda_compiler_version",
                                "cdt_name",
                                "docker_image",
                            ],
                            ["libgrpc", "libprotobuf"],
                        ],
                    ),
                ]
            ),
            dict(
                [
                    (
                        "extend_keys",
                        {
                            "extend_keys",
                            "ignore_build_only_deps",
                            "ignore_version",
                            "pin_run_as_build",
                        },
                    ),
                    ("ignore_build_only_deps", {"python", "numpy"}),
                    (
                        "pin_run_as_build",
                        dict(
                            [
                                (
                                    "python",
                                    {"max_pin": "x.x", "min_pin": "x.x"},
                                ),
                                (
                                    "r-base",
                                    {"max_pin": "x.x", "min_pin": "x.x"},
                                ),
                                ("flann", {"max_pin": "x.x.x"}),
                                ("graphviz", {"max_pin": "x"}),
                                ("libsvm", {"max_pin": "x"}),
                                ("netcdf-cxx4", {"max_pin": "x.x"}),
                                ("occt", {"max_pin": "x.x"}),
                                ("poppler", {"max_pin": "x.x"}),
                                ("vlfeat", {"max_pin": "x.x.x"}),
                            ]
                        ),
                    ),
                    ("glew", ["2.1"]),
                    ("pango", ["1.50"]),
                    ("libgoogle_cloud_compute_devel", ["2.21"]),
                    ("dav1d", ["1.2.1"]),
                    ("lzo", ["2"]),
                    ("pybind11_abi", ["4"]),
                    ("sqlite", ["3"]),
                    ("nlopt", ["2.7"]),
                    ("aws_checksums", ["0.1.18"]),
                    ("aws_c_mqtt", ["0.10.2"]),
                    ("aws_c_s3", ["0.5.1"]),
                    ("libaec", ["1"]),
                    ("pari", ["2.15.* *_pthread"]),
                    ("libgoogle_cloud_devel", ["2.21"]),
                    ("libjpeg_turbo", ["3"]),
                    ("libblitz", ["1.0.2"]),
                    ("ptscotch", ["7.0.4"]),
                    ("openslide", ["4"]),
                    ("libdeflate", ["1.19"]),
                    ("gf2x", ["1.3"]),
                    ("cuda_compiler_version_min", ["11.2"]),
                    ("aws_c_event_stream", ["0.4.2"]),
                    ("arb", ["2.23"]),
                    ("expat", ["2"]),
                    ("bzip2", ["1"]),
                    ("target_goexe", [""]),
                    ("VERBOSE_AT", ["V=1"]),
                    ("cran_mirror", ["https://cran.r-project.org"]),
                    ("aws_c_compression", ["0.2.18"]),
                    ("libsvm", ["332"]),
                    ("uhd", ["4.6.0"]),
                    ("libcrc32c", ["1.1"]),
                    ("libtensorflow_cc", ["2.15"]),
                    ("msgpack_cxx", ["6"]),
                    ("libunwind", ["1.6"]),
                    ("libv8", ["8.9.83"]),
                    ("libpq", ["16"]),
                    ("lmdb", ["0.9.29"]),
                    ("root_base", ["6.28.10", "6.30.2"]),
                    ("geotiff", ["1.7.1"]),
                    ("google_cloud_cpp", ["2.21"]),
                    ("mpfr", ["4"]),
                    ("gmp", ["6"]),
                    ("harfbuzz", ["8"]),
                    ("_libgcc_mutex", ["0.1 conda_forge"]),
                    ("wxwidgets", ["3.2"]),
                    ("svt_av1", ["1.8.0"]),
                    ("libcurl", ["8"]),
                    ("liblapack", ["3.9 *netlib"]),
                    ("libmatio_cpp", ["0.2.3"]),
                    ("libvips", ["8"]),
                    ("aws_sdk_cpp", ["1.11.267"]),
                    ("proj", ["9.3.1"]),
                    ("libgoogle_cloud_all_devel", ["2.21"]),
                    ("libgoogle_cloud_aiplatform_devel", ["2.21"]),
                    ("libpcap", ["1.10"]),
                    ("pulseaudio_client", ["16.1"]),
                    ("ffmpeg", ["6"]),
                    ("graphviz", ["9"]),
                    ("cudnn", ["8"]),
                    ("x264", ["1!164.*"]),
                    ("libcint", ["5.5"]),
                    ("s2n", ["1.4.4"]),
                    ("sdl2_ttf", ["2"]),
                    ("pugixml", ["1.14"]),
                    ("flatbuffers", ["23.5.26"]),
                    ("krb5", ["1.20"]),
                    ("ntl", ["11.4.3"]),
                    ("libev", ["4.33"]),
                    ("aws_c_io", ["0.14.4"]),
                    ("target_gobin", ["${PREFIX}/bin/"]),
                    ("cxx_compiler", ["gxx"]),
                    ("ccr", ["1.3"]),
                    ("postgresql", ["16"]),
                    ("antic", ["0.2"]),
                    ("gst_plugins_base", ["1.22"]),
                    ("rdma_core", ["49"]),
                    ("libssh2", ["1"]),
                    ("libtiff", ["4.6"]),
                    ("kealib", ["1.5"]),
                    ("mpich", ["4"]),
                    ("spdlog", ["1.12"]),
                    ("netcdf_fortran", ["4.6"]),
                    ("elfutils", ["0.190"]),
                    ("gsl", ["2.7"]),
                    ("eclib", ["20231211"]),
                    ("tiledb", ["2.20"]),
                    ("libhugetlbfs", ["2"]),
                    ("nss", ["3"]),
                    ("netcdf_cxx4", ["4.3"]),
                    ("pcl", ["1.13.1"]),
                    ("sox", ["14.4.2"]),
                    ("superlu_dist", ["8"]),
                    ("libgoogle_cloud_dialogflow_es_devel", ["2.21"]),
                    ("attr", ["2.5"]),
                    ("log4cxx", ["1.2.0"]),
                    ("aws_c_sdkutils", ["0.1.15"]),
                    ("libxml2", ["2"]),
                    ("libsentencepiece", ["0.1.99"]),
                    ("tbb_devel", ["2021"]),
                    ("jsoncpp", ["1.9.5"]),
                    ("msgpack_c", ["6"]),
                    ("libzip", ["1"]),
                    ("mkl", ["2023"]),
                    ("giflib", ["5.2"]),
                    ("fortran_compiler", ["gfortran"]),
                    ("libboost_python_devel", ["1.82"]),
                    ("dbus", ["1"]),
                    ("libwebp_base", ["1"]),
                    ("libflint", ["2.9"]),
                    ("libsoup", ["3"]),
                    ("libgoogle_cloud_bigtable_devel", ["2.21"]),
                    ("abseil_cpp", ["20220623.0"]),
                    ("librdkafka", ["2.2"]),
                    ("starlink_ast", ["9.2.7"]),
                    ("lerc", ["4"]),
                    ("davix", ["0.8"]),
                    ("libxsmm", ["1"]),
                    ("poppler", ["23.07"]),
                    ("dcap", ["2.47"]),
                    ("gnuradio_core", ["3.10.9"]),
                    ("gsoap", ["2.8.123"]),
                    ("fmt", ["10"]),
                    ("libopencv", ["4.9.0"]),
                    ("aws_c_http", ["0.8.1"]),
                    ("lua", ["5"]),
                    ("qt", ["5.15"]),
                    ("pcre", ["8"]),
                    ("ldas_tools_framecpp", ["2.9"]),
                    ("ruby", ["2.6", "2.5"]),
                    ("libgoogle_cloud_policytroubleshooter_devel", ["2.21"]),
                    ("libdap4", ["3.20.6"]),
                    ("mimalloc", ["2.1.2"]),
                    ("coin_or_osi", ["0.108"]),
                    ("gdk_pixbuf", ["2"]),
                    ("target_goarch", ["amd64"]),
                    ("assimp", ["5.3.1"]),
                    ("flann", ["1.9.2"]),
                    ("gct", ["6.2.1629922860"]),
                    ("aws_c_auth", ["0.7.16"]),
                    ("pyqtchart", ["5.15"]),
                    ("coin_or_clp", ["1.17"]),
                    ("grpc_cpp", ["1.52"]),
                    ("libgdal", ["3.8"]),
                    ("volk", ["3.1"]),
                    ("curl", ["8"]),
                    ("geos", ["3.12.1"]),
                    ("zstd", ["1.5"]),
                    ("libabseil", ["20240116"]),
                    ("blas_impl", ["openblas", "mkl", "blis"]),
                    ("openblas", ["0.3.*"]),
                    ("zlib_ng", ["2.0"]),
                    ("liblapacke", ["3.9 *netlib"]),
                    ("libframel", ["8.41"]),
                    ("postgresql_plpython", ["16"]),
                    ("libgoogle_cloud", ["2.21"]),
                    ("gstreamer", ["1.22"]),
                    ("lcms", ["2"]),
                    ("libuuid", ["2"]),
                    ("coin_or_cgl", ["0.60"]),
                    ("rust_compiler", ["rust"]),
                    ("bullet_cpp", ["3.25"]),
                    ("fftw", ["3"]),
                    ("tbb", ["2021"]),
                    ("libsecret", ["0.18"]),
                    ("libgoogle_cloud_spanner_devel", ["2.21"]),
                    ("channel_sources", ["conda-forge"]),
                    ("pcre2", ["10.42"]),
                    ("glib", ["2"]),
                    ("google_cloud_cpp_common", ["0.25.0"]),
                    ("openmpi", ["4"]),
                    ("ncurses", ["6"]),
                    ("openh264", ["2.4.1"]),
                    ("wcslib", ["8"]),
                    ("soapysdr", ["0.8"]),
                    ("tinyxml2", ["10"]),
                    ("libavif", ["1.0.1"]),
                    ("cairo", ["1"]),
                    ("icu", ["73"]),
                    ("libsndfile", ["1.2"]),
                    ("aom", ["3.7"]),
                    ("x265", ["3.5"]),
                    ("jasper", ["4"]),
                    ("pyqt", ["5.15"]),
                    ("xrootd", ["5"]),
                    ("gnutls", ["3.7"]),
                    ("rocksdb", ["8.0"]),
                    ("libgit2", ["1.7"]),
                    ("libgoogle_cloud_oauth2_devel", ["2.21"]),
                    ("zfp", ["1.0"]),
                    ("libtorch", ["2.1"]),
                    ("libarchive", ["3.7"]),
                    ("freetype", ["2"]),
                    ("poco", ["1.13.2"]),
                    ("libthrift", ["0.19.0"]),
                    ("qt_main", ["5.15"]),
                    ("libosqp", ["0.6.3"]),
                    ("ucx", ["1.15.0"]),
                    ("libgoogle_cloud_automl_devel", ["2.21"]),
                    ("slepc", ["3.20"]),
                    ("aws_c_cal", ["0.6.10"]),
                    ("p11_kit", ["0.24"]),
                    ("target_platform", ["linux-64"]),
                    ("libblas", ["3.9 *netlib"]),
                    ("libgoogle_cloud_bigquery_devel", ["2.21"]),
                    ("libmicrohttpd", ["1.0"]),
                    ("mpg123", ["1.32"]),
                    ("srm_ifce", ["1.24.6"]),
                    ("petsc", ["3.20"]),
                    ("libiconv", ["1"]),
                    ("aws_crt_cpp", ["0.26.2"]),
                    ("console_bridge", ["1.0"]),
                    ("libgoogle_cloud_storage_devel", ["2.21"]),
                    ("lz4_c", ["1.9.3"]),
                    ("mumps_mpi", ["5.6.2"]),
                    ("coincbc", ["2.10"]),
                    ("orc", ["1.9.2"]),
                    ("libcblas", ["3.9 *netlib"]),
                    ("readline", ["8"]),
                    ("nodejs", ["18", "20"]),
                    ("glpk", ["5.0"]),
                    ("imath", ["3.1.9"]),
                    ("gdal", ["3.8"]),
                    ("nettle", ["3.9"]),
                    ("qtkeychain", ["0.14"]),
                    ("c_ares", ["1"]),
                    ("libduckdb_devel", ["0.9.2"]),
                    ("occt", ["7.7.2"]),
                    ("qt6_main", ["6.6"]),
                    ("perl", ["5.32.1"]),
                    ("libidn2", ["2"]),
                    ("pyqtwebengine", ["5.15"]),
                    ("coin_or_utils", ["2.11"]),
                    ("libopenvino_dev", ["2023.3.0"]),
                    ("googleapis_cpp", ["0.10"]),
                    ("libwebp", ["1"]),
                    ("coin_or_cbc", ["2.10"]),
                    ("channel_targets", ["conda-forge main"]),
                    ("sdl2_image", ["2"]),
                    ("sdl2_mixer", ["2"]),
                    ("vtk", ["9.2.6"]),
                    ("librsvg", ["2"]),
                    ("jpeg", ["9"]),
                    ("hdf4", ["4.2.15"]),
                    ("pytorch", ["2.1"]),
                    ("libintervalxt", ["3"]),
                    ("thrift_cpp", ["0.19.0"]),
                    ("libgoogle_cloud_discoveryengine_devel", ["2.21"]),
                    ("arpack", ["3.8"]),
                    ("libtensorflow", ["2.15"]),
                    ("vlfeat", ["0.9.21"]),
                    ("snappy", ["1"]),
                    ("capnproto", ["0.10.2"]),
                    ("libmatio", ["1.5.26"]),
                    ("c_compiler", ["gcc"]),
                    ("cgo_compiler", ["go-cgo"]),
                    ("ipopt", ["3.14.14"]),
                    ("libiio", ["0"]),
                    ("singular", ["4.3.2.p8"]),
                    ("libhwy", ["1.0"]),
                    ("zeromq", ["4.3.5"]),
                    ("pixman", ["0"]),
                    ("libspatialindex", ["1.9.3"]),
                    ("libffi", ["3.4"]),
                    ("nspr", ["4"]),
                    ("petsc4py", ["3.20"]),
                    ("libsqlite", ["3"]),
                    ("pulseaudio", ["16.1"]),
                    ("libopentelemetry_cpp", ["1.14"]),
                    ("libptscotch", ["7.0.4"]),
                    ("libraw", ["0.21"]),
                    ("libgoogle_cloud_dlp_devel", ["2.21"]),
                    ("libgoogle_cloud_iam_devel", ["2.21"]),
                    ("openjpeg", ["2"]),
                    ("libhwloc", ["2.9.1"]),
                    ("r_base", ["4.2", "4.3"]),
                    ("gfal2", ["2.21"]),
                    ("libexactreal", ["4"]),
                    ("mkl_devel", ["2023"]),
                    ("zlib", ["1.2"]),
                    ("libmed", ["4.1"]),
                    ("fontconfig", ["2"]),
                    ("xz", ["5"]),
                    ("suitesparse", ["5"]),
                    ("libgoogle_cloud_speech_devel", ["2.21"]),
                    ("sdl2_net", ["2"]),
                    ("slepc4py", ["3.20"]),
                    ("tk", ["8.6"]),
                    ("libpng", ["1.6"]),
                    ("libssh", ["0.10"]),
                    ("urdfdom", ["3.1"]),
                    ("metis", ["5.1.0"]),
                    ("libnetcdf", ["4.9.2"]),
                    ("sdl2", ["2"]),
                    ("target_goos", ["linux"]),
                    ("cfitsio", ["4.3.0"]),
                    ("pulseaudio_daemon", ["16.1"]),
                    ("mumps_seq", ["5.6.2"]),
                    ("hdf5", ["1.14.3"]),
                    ("nccl", ["2"]),
                    ("libevent", ["2.1.12"]),
                    ("exiv2", ["0.27"]),
                    ("libeantic", ["2"]),
                    ("alsa_lib", ["1.2.10"]),
                    ("glog", ["0.7"]),
                    ("libscotch", ["7.0.4"]),
                    ("cutensor", ["2"]),
                    ("json_c", ["0.17"]),
                    ("aws_c_common", ["0.9.13"]),
                    ("isl", ["0.26"]),
                    ("openssl", ["3"]),
                    ("xerces_c", ["3.2"]),
                    ("cpu_optimization_target", ["nocona"]),
                    ("libflatsurf", ["3"]),
                    ("libkml", ["1.3"]),
                    ("gflags", ["2.2"]),
                    ("libboost_devel", ["1.82"]),
                    ("libgoogle_cloud_dialogflow_cx_devel", ["2.21"]),
                    ("VERBOSE_CM", ["VERBOSE=1"]),
                    ("openexr", ["3.2"]),
                    ("scotch", ["7.0.4"]),
                    ("libgoogle_cloud_pubsub_devel", ["2.21"]),
                    ("libabseil_static", ["20220623.0"]),
                    ("go_compiler", ["go-nocgo"]),
                    ("re2", ["2023.06.02"]),
                    ("tensorflow", ["2.15"]),
                    ("libarrow_all", ("12", "14", "13", "15")),
                    ("arrow_cpp", ("12", "14", "13", "15")),
                    ("libarrow", ("12", "14", "13", "15")),
                    ("c_compiler_version", ("10", "12")),
                    ("fortran_compiler_version", ("10", "12")),
                    ("cdt_name", ("cos7", "cos6")),
                    (
                        "docker_image",
                        (
                            "quay.io/condaforge/linux-anvil-cuda:11.2",
                            "quay.io/condaforge/linux-anvil-cos7-x86_64",
                        ),
                    ),
                    ("cuda_compiler", ("nvcc", "None")),
                    ("cxx_compiler_version", ("10", "12")),
                    ("cuda_compiler_version", ("11.2", "None")),
                    ("libgrpc", ("1.61",)),
                    ("libprotobuf", ("4.25.2",)),
                    ("c_stdlib_version", ("2.12",)),
                    ("c_stdlib", ("sysroot",)),
                    (
                        "python",
                        (
                            "3.9.* *_cpython",
                            "3.10.* *_cpython",
                            "3.11.* *_cpython",
                            "3.8.* *_cpython",
                            "3.12.* *_cpython",
                        ),
                    ),
                    ("numpy", ("1.22", "1.22", "1.23", "1.22", "1.26")),
                    (
                        "python_impl",
                        (
                            "cpython",
                            "cpython",
                            "cpython",
                            "cpython",
                            "cpython",
                        ),
                    ),
                    (
                        "zip_keys",
                        [
                            ("arrow_cpp", "libarrow", "libarrow_all"),
                            (
                                "c_compiler_version",
                                "cxx_compiler_version",
                                "fortran_compiler_version",
                                "cuda_compiler",
                                "cuda_compiler_version",
                                "cdt_name",
                                "docker_image",
                            ),
                            ("c_stdlib", "c_stdlib_version"),
                            ("libgrpc", "libprotobuf"),
                            ("python", "numpy", "python_impl"),
                        ],
                    ),
                ]
            ),
            {
                "BUILD",
                "MACOSX_DEPLOYMENT_TARGET",
                "MACOSX_SDK_VERSION",
                "build_number_decrement",
                "c_compiler",
                "c_compiler_version",
                "cdt_arch",
                "cdt_name",
                "channel_sources",
                "channel_targets",
                "cuda_compiler",
                "cuda_compiler_version",
                "docker_image",
                "macos_machine",
                "macos_min_version",
                "pin_run_as_build",
                "target_platform",
                "zip_keys",
            },
            {
                "c_compiler": ["gcc"],
                "c_compiler_version": ["10", "12"],
                "cdt_name": ["cos7", "cos6"],
                "channel_sources": ["conda-forge"],
                "channel_targets": ["conda-forge main"],
                "cuda_compiler": ["nvcc", "None"],
                "cuda_compiler_version": ["11.2", "None"],
                "docker_image": [
                    "quay.io/condaforge/linux-anvil-cuda:11.2",
                    "quay.io/condaforge/linux-anvil-cos7-x86_64",
                ],
                "pin_run_as_build": dict(
                    [
                        ("python", {"max_pin": "x.x", "min_pin": "x.x"}),
                        ("r-base", {"max_pin": "x.x", "min_pin": "x.x"}),
                        ("flann", {"max_pin": "x.x.x"}),
                        ("graphviz", {"max_pin": "x"}),
                        ("libsvm", {"max_pin": "x"}),
                        ("netcdf-cxx4", {"max_pin": "x.x"}),
                        ("occt", {"max_pin": "x.x"}),
                        ("poppler", {"max_pin": "x.x"}),
                        ("vlfeat", {"max_pin": "x.x.x"}),
                    ]
                ),
                "target_platform": ["linux-64"],
                "zip_keys": [
                    ("arrow_cpp", "libarrow", "libarrow_all"),
                    (
                        "c_compiler_version",
                        "cxx_compiler_version",
                        "fortran_compiler_version",
                        "cuda_compiler",
                        "cuda_compiler_version",
                        "cdt_name",
                        "docker_image",
                    ),
                    ("c_stdlib", "c_stdlib_version"),
                    ("libgrpc", "libprotobuf"),
                    ("python", "numpy", "python_impl"),
                ],
            },
        )
    ],
)
def test_get_used_key_values_by_input_order(
    squished_input_variants,
    squished_used_variants,
    all_used_vars,
    expected_used_key_values,
):
    used_key_values, _ = (
        configure_feedstock._get_used_key_values_by_input_order(
            squished_input_variants,
            squished_used_variants,
            all_used_vars,
        )
    )
    assert used_key_values == expected_used_key_values


def test_conda_build_api_render_for_smithy(testing_workdir):
    import conda_build.api

    _thisdir = os.path.abspath(os.path.dirname(__file__))
    recipe = os.path.join(_thisdir, "recipes", "multiple_outputs")
    dest_recipe = os.path.join(testing_workdir, "recipe")
    shutil.copytree(recipe, dest_recipe)
    all_top_level_builds = {
        ("1.5", "9.5"),
        ("1.5", "9.6"),
        ("1.6", "9.5"),
        ("1.6", "9.6"),
    }

    cs_metas = configure_feedstock._conda_build_api_render_for_smithy(
        dest_recipe,
        config=None,
        variants=None,
        permit_unsatisfiable_variants=True,
        finalize=False,
        bypass_env_check=True,
        platform="linux",
        arch="64",
    )
    # we have a build matrix with 4 combinations and we get two outputs
    # plus a top-level build to give us 4 * (2 + 1) = 12 total
    assert len(cs_metas) == 12

    # we check that we get all combinations
    top_level_builds = set()
    for meta, _, _ in cs_metas:
        for variant in meta.config.variants:
            top_level_builds.add(
                (
                    variant.get("libpng"),
                    variant.get("libpq"),
                )
            )
        variant = meta.config.variant
        top_level_builds.add(
            (
                variant.get("libpng"),
                variant.get("libpq"),
            )
        )
    assert len(top_level_builds) == len(all_top_level_builds)
    assert top_level_builds == all_top_level_builds
    cb_metas = conda_build.api.render(
        dest_recipe,
        config=None,
        variants=None,
        permit_unsatisfiable_variants=True,
        finalize=False,
        bypass_env_check=True,
        platform="linux",
        arch="64",
    )
    # conda build will only give us the builds for the unique file names
    # and collapses the top-level build matrix expansion
    # thus we only get 3 outputs
    assert len(cb_metas) == 3

    # we check that we get a subset of all combinations
    top_level_builds = set()
    for meta, _, _ in cb_metas:
        for variant in meta.config.variants:
            top_level_builds.add(
                (
                    variant.get("libpng"),
                    variant.get("libpq"),
                )
            )
        variant = meta.config.variant
        top_level_builds.add(
            (
                variant.get("libpng"),
                variant.get("libpq"),
            )
        )
    assert len(top_level_builds) < len(all_top_level_builds)
    assert top_level_builds.issubset(all_top_level_builds)


def test_github_actions_pins():
    """
    Ensure our Github Actions template respects the latest pins provided by Dependabot.
    Since Dependabot cannot parse the template due to the Jinja expressions, we provide
    a proxy file with the inventory of used actions.

    This test will check that the `uses: owner/repo@version` lines are the same in both files.
    If Dependabot opens a PR against the proxy, just copy the new pins to the template to
    make this pass.
    """
    repo_root = Path(__file__).parents[1]
    github_actions_template = (
        repo_root / "conda_smithy" / "templates" / "github-actions.yml.tmpl"
    )
    dependabot_inventory = (
        repo_root
        / ".github"
        / "workflows"
        / "_proxy-file-for-dependabot-tests.yml"
    )

    def get_uses(path):
        content = path.read_text()
        for line in content.splitlines():
            if " uses: " in line:
                yield line.strip().lstrip("-").strip()

    assert sorted(set(get_uses(github_actions_template))) == sorted(
        set(get_uses(dependabot_inventory))
    )
