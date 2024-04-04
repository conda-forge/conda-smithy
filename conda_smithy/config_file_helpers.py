from pathlib import Path
from typing import Optional

try:
    from enum import StrEnum
except ImportError:
    from backports.strenum import StrEnum

from conda_smithy.utils import get_yaml


class MultipleConfigFilesError(ValueError):
    """
    Raised when multiple configuration files are found in different locations and only one is allowed.
    """

    pass


class ConfigFileMustBeDictError(ValueError):
    """
    Raised when a configuration file does not represent a dictionary.
    """

    pass


class ConfigFileName(StrEnum):
    CONDA_FORGE_YML = "conda-forge.yml"
    CONDA_BUILD_CONFIG = "conda_build_config.yaml"


def read_local_config_file(
    recipe_dir: Path, filename: ConfigFileName, enforce_one: bool = True
) -> dict:
    """
    Read a local YAML configuration file from the recipe directory.
    It is assumed that the local configuration file has a dictionary-like structure.
    Multiple relative paths are checked for the file in a specific order.

    :param recipe_dir: the recipe directory of a feedstock
    :param filename: the name of the configuration file
    :param enforce_one: if True, only one config file with the given name is allowed when looking for it in different
    locations. If False, the contents of the first file found is returned.

    :raises FileNotFoundError if the file does not exist in all possible locations
    :raises ConfigFileMustBeDictError if the file does not represent a dictionary
    (takes precedence over MultipleConfigFilesError)
    :raises MultipleConfigFilesError if multiple files are found and only one is allowed
    """

    file_candidates = [
        recipe_dir / filename,
        recipe_dir / ".." / filename,
        recipe_dir / ".." / ".." / filename,
    ]

    file_contents: Optional[dict] = None

    for file in file_candidates:
        if file_contents is not None and file.exists():
            # we know that enforce_one is True since otherwise we would have returned already
            raise MultipleConfigFilesError(
                f"Multiple configuration files '{filename}' found in different locations relative to {recipe_dir}."
            )

        try:
            file_contents = get_yaml().load(file)
        except FileNotFoundError:
            continue

        if not isinstance(file_contents, dict):
            raise ConfigFileMustBeDictError(
                f"The YAML configuration file '{file}' does not represent a dictionary."
            )

        if not enforce_one:
            # early return
            return file_contents

    if file_contents is not None:
        return file_contents

    raise FileNotFoundError(
        f"No {filename} file found in any of the following locations: {', '.join(map(str, file_candidates))}"
    )
