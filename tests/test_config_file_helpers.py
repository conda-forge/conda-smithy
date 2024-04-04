import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from conda_smithy.config_file_helpers import (
    read_local_config_file,
    ConfigFileName,
    ConfigFileMustBeDictError,
    MultipleConfigFilesError,
)


@contextmanager
def tmp_directory() -> Path:
    with tempfile.TemporaryDirectory(prefix="recipe_") as tmp_dir:
        yield Path(tmp_dir)


@contextmanager
def nested_tmp_directory():
    """
    Create two nested directories within a temporary directory.
    """
    with tmp_directory() as tmp_dir:
        child_dir = tmp_dir / "child1" / "child2"
        child_dir.mkdir(parents=True)
        yield child_dir


class TestReadLocalConfigFile(unittest.TestCase):

    def test_empty_dir(self):
        with nested_tmp_directory() as recipe_dir:
            with self.assertRaises(FileNotFoundError):
                read_local_config_file(
                    recipe_dir, ConfigFileName.CONDA_FORGE_YML
                )

    def test_multiple_files(self):
        with nested_tmp_directory() as recipe_dir:
            with open(recipe_dir / "conda-forge.yml", "w") as fh:
                fh.write("package:\n  name: foo")
            with open(recipe_dir / ".." / "conda-forge.yml", "w") as fh:
                fh.write("package:\n  name: bar")

            with self.assertRaises(MultipleConfigFilesError) as e:
                read_local_config_file(
                    recipe_dir, ConfigFileName.CONDA_FORGE_YML
                )
            self.assertIn("Multiple configuration files", str(e.exception))

    def test_precedence_1(self):
        with nested_tmp_directory() as recipe_dir:
            with open(recipe_dir / ".." / "conda-forge.yml", "w") as fh:
                fh.write("package:\n  name: DO_NOT_USE_1")
            with open(recipe_dir / "conda-forge.yml", "w") as fh:
                fh.write("package:\n  name: foo")
            with open(recipe_dir / ".." / ".." / "conda-forge.yml", "w") as fh:
                fh.write("package:\n  name: DO_NOT_USE_2")

            forge_yml = read_local_config_file(
                recipe_dir, ConfigFileName.CONDA_FORGE_YML, enforce_one=False
            )

        self.assertEqual(forge_yml["package"]["name"], "foo")

    def test_precedence_2(self):
        with nested_tmp_directory() as recipe_dir:
            with open(recipe_dir / ".." / "conda-forge.yml", "w") as fh:
                fh.write("package:\n  name: foo")
            with open(recipe_dir / ".." / ".." / "conda-forge.yml", "w") as fh:
                fh.write("package:\n  name: DO_NOT_USE_2")

            forge_yml = read_local_config_file(
                recipe_dir, ConfigFileName.CONDA_FORGE_YML, enforce_one=False
            )

        self.assertEqual(forge_yml["package"]["name"], "foo")

    def test_precedence_3(self):
        with nested_tmp_directory() as recipe_dir:
            with open(recipe_dir / ".." / ".." / "conda-forge.yml", "w") as fh:
                fh.write("package:\n  name: foo")

            forge_yml = read_local_config_file(
                recipe_dir, ConfigFileName.CONDA_FORGE_YML
            )

        self.assertEqual(forge_yml["package"]["name"], "foo")

    def test_no_dict(self):
        with nested_tmp_directory() as recipe_dir:
            with open(recipe_dir / "conda-forge.yml", "w") as fh:
                fh.write("foo")

            with self.assertRaises(ConfigFileMustBeDictError) as e:
                read_local_config_file(
                    recipe_dir, ConfigFileName.CONDA_FORGE_YML
                )
            self.assertIn("does not represent a dict", str(e.exception))
