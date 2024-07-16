import pytest

from conda_smithy.ci_skeleton import generate


def test_generate(tmpdir, snapshot):
    generate(
        package_name="my-package",
        feedstock_directory=str(tmpdir),
        recipe_directory="myrecipe",
    )
    with open(tmpdir / "conda-forge.yml") as f:
        conda_forge_yml = f.read()
    assert conda_forge_yml == snapshot(name="CONDA_FORGE_YML")
    with open(tmpdir / "myrecipe" / "meta.yaml") as f:
        meta_yaml = f.read()
    assert meta_yaml == snapshot(name="META_YML")
    with open(tmpdir / ".gitignore") as f:
        gitignore = f.read()
    assert gitignore == snapshot(name="gitignore")
