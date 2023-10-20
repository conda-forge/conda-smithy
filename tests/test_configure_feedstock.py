import os
import conda_smithy.configure_feedstock as cnfgr_fdstk

import pytest
import copy
import yaml
import textwrap


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


@pytest.mark.parametrize("recipe_dirname", ["recipe", "custom_recipe_dir"])
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
    # 2 python versions. Recipe uses c_compiler, but this is a zipped key
    #     and shouldn't add extra configurations
    assert len(os.listdir(matrix_dir)) == 2


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


def test_py_matrix_on_github(py_recipe, jinja_env):
    py_recipe.config["provider"]["linux"] = "github_actions"

    cnfgr_fdstk.render_github_actions(
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
    assert len(os.listdir(matrix_dir)) == 6


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
        content = yaml.safe_load(fp)
    assert "%APPVEYOR_REPO_BRANCH%" in content["deploy_script"][0]
    assert "UPLOAD_ON_BRANCH=foo-branch" in content["deploy_script"][-2]


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
    circle_osx_file = os.path.join(forge_dir, ".scripts", "run_osx_build.sh")
    circle_linux_file = os.path.join(
        forge_dir, ".scripts", "run_docker_build.sh"
    )
    circle_config_file = os.path.join(forge_dir, ".circleci", "config.yml")

    cnfgr_fdstk.clear_scripts(forge_dir)
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

    cnfgr_fdstk.clear_scripts(forge_dir)
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

    cnfgr_fdstk.clear_scripts(forge_dir)
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
    circle_osx_file = os.path.join(forge_dir, ".scripts", "run_osx_build.sh")
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


def test_secrets(py_recipe, jinja_env):
    cnfgr_fdstk.render_azure(
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
    cnfgr_fdstk.render_drone(
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
    cnfgr_fdstk.render_azure(
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
    cnfgr_fdstk.render_azure(
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
    cnfgr_fdstk.render_azure(
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

    assert "win_64_c_compilervs2008python2.7.yaml" in rendered_variants
    assert "win_64_c_compilervs2017python3.5.yaml" in rendered_variants


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
        ".github/workflows/webservices.yml",
    ]
    for f in skipped_files:
        fpath = os.path.join(render_skipped_recipe.recipe, f)
        assert not os.path.exists(fpath)


def test_choco_install(choco_recipe, jinja_env):
    cnfgr_fdstk.render_azure(
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
    cnfgr_fdstk.render_github_actions_services(
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
    cnfgr_fdstk.render_github_actions_services(
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
    load_forge_config = lambda: cnfgr_fdstk._load_forge_config(  # noqa
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


def test_noarch_platforms_bad_yaml(config_yaml):
    load_forge_config = lambda: cnfgr_fdstk._load_forge_config(  # noqa
        config_yaml,
        exclusive_config_file=os.path.join(
            config_yaml, "recipe", "default_config.yaml"
        ),
    )

    with open(os.path.join(config_yaml, "conda-forge.yml"), "a+") as fp:
        fp.write("noarch_platforms: [eniac, zx80]")

    with pytest.raises(ValueError) as excinfo:
        load_forge_config()

    assert "eniac" in str(excinfo.value)


def test_forge_yml_alt_path(config_yaml):
    load_forge_config = (
        lambda forge_yml: cnfgr_fdstk._load_forge_config(  # noqa
            config_yaml,
            exclusive_config_file=os.path.join(
                config_yaml, "recipe", "default_config.yaml"
            ),
            forge_yml=forge_yml,
        )
    )

    forge_yml = os.path.join(config_yaml, "conda-forge.yml")
    forge_yml_alt = os.path.join(
        config_yaml, ".config", "feedstock-config.yml"
    )

    os.mkdir(os.path.dirname(forge_yml_alt))
    os.rename(forge_yml, forge_yml_alt)

    with pytest.raises(RuntimeError):
        load_forge_config(None)

    assert load_forge_config(forge_yml_alt)["recipe_dir"] == "recipe"


def test_cos7_env_render(py_recipe, jinja_env):
    forge_config = copy.deepcopy(py_recipe.config)
    forge_config["os_version"] = {"linux_64": "cos7"}
    has_env = "DEFAULT_LINUX_VERSION" in os.environ
    if has_env:
        old_val = os.environ["DEFAULT_LINUX_VERSION"]
        del os.environ["DEFAULT_LINUX_VERSION"]

    try:
        assert "DEFAULT_LINUX_VERSION" not in os.environ
        cnfgr_fdstk.render_azure(
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
        cnfgr_fdstk.render_azure(
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


def test_conda_build_tools(config_yaml):
    load_forge_config = lambda: cnfgr_fdstk._load_forge_config(  # noqa
        config_yaml,
        exclusive_config_file=os.path.join(
            config_yaml, "recipe", "default_config.yaml"
        ),
    )

    cfg = load_forge_config()
    assert (
        "build_with_mambabuild" not in cfg
    )  # superseded by conda_build_tool=mambabuild
    assert cfg["conda_build_tool"] == "mambabuild"  # current default

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

    with pytest.raises(AssertionError):
        assert load_forge_config()


def test_remote_ci_setup(config_yaml):
    load_forge_config = lambda: cnfgr_fdstk._load_forge_config(  # noqa
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
    assert cfg["remote_ci_setup_update"] == ["conda-forge-ci-setup", "py-lief"]

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
