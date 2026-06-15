import subprocess
import sys
import textwrap
from pathlib import Path

import pygit2
import pytest

from conda_smithy import configure_feedstock
from conda_smithy.feedstock_io import get_repo

EXECUTABLE_TEMPLATES = [
    ".scripts/SetPageFileSize.ps1",
    ".scripts/build_steps.sh",
    ".scripts/create_conda_build_artifacts.bat",
    ".scripts/create_conda_build_artifacts.sh",
    ".scripts/create_pagefile.bat",
    ".scripts/create_pagefile.sh",
    ".scripts/free_disk_space.sh",
    ".scripts/run_docker_build.sh",
    ".scripts/run_osx_build.sh",
    ".scripts/run_win_build.bat",
]


ALL_EXECUTABLE_FILES = EXECUTABLE_TEMPLATES + [
    ".circleci/checkout_merge_commit.sh",
    ".circleci/fast_finish_ci_pr_build.sh",
    "build-locally.py",
    ".azure-pipelines/azure-pipelines-linux.yml",
    ".azure-pipelines/azure-pipelines-osx.yml",
    ".azure-pipelines/azure-pipelines-win.yml",
]


@pytest.mark.parametrize("provider", ["azure", "github_actions", "drone", "travis"])
def test_exec_bits(py_recipe, jinja_env, provider):
    forge_dir = py_recipe.recipe
    forge_yml = Path(forge_dir, "conda-forge.yml")
    with open(forge_yml, "a") as f:
        f.write(textwrap.dedent(f"""\
            provider:
              # travis not allowed for linux_64
              linux_aarch64: {provider}
              # osx_64: {provider if provider not in ["drone", "travis"] else "default"}
              # win_64: {provider if provider not in ["drone", "travis"] else "default"}
        """))

    # initialize a git repo (we want to check exec bits as commited by rerender)
    subprocess.call(
        'git init && git add . && git commit -m "initial commit"',
        cwd=forge_dir,
        shell=True,
        stdout=sys.stderr,
    )

    configure_feedstock.main(
        forge_file_directory=forge_dir,
        forge_yml=forge_yml,
        no_check_uptodate=True,
        commit=True,
    )

    # sanity check for pytest failure logs: check content of recipe folder
    subprocess.call(["ls", "-lla"], cwd=forge_dir, stdout=sys.stderr)
    repo = get_repo(forge_dir)

    def is_executable(file):
        entry = repo.index[file]
        return entry.mode == pygit2.GIT_FILEMODE_BLOB_EXECUTABLE

    def iter_files(root_dir):
        # traverse through all subfolders, only return actual files, nothing from .git/
        for p in Path(root_dir).rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(root_dir)
            if ".git" in rel.parts:
                continue
            yield rel

    for file in iter_files(forge_dir):
        # we expect all executable files to have the exec bit,
        # and all non-exectutable files to not have it
        assert is_executable(file) == (str(file) in ALL_EXECUTABLE_FILES)
