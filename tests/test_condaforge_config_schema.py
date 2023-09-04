import pytest
from pydantic import ValidationError
import yaml
from conda_smithy.schema.models import ConfigModel


# Sample config files
SAMPLE_CONFIGS = [
    {
        "github": {
            "branch_name": "main",
            "tooling_branch_name": "main",
        },
        "conda_forge_output_validation": True,
        "conda_build": {
            "pkg_format": "2",
        },
    },
    {
        "travis": {
            "secure": {
                "BINSTAR_TOKEN": "your_secure_token_here",
            },
        },
        "conda_forge_output_validation": True,
        "github": {
            "branch_name": "main",
            "tooling_branch_name": "main",
        },
        "conda_build": {
            "pkg_format": "2",
        },
    },
    {
        "build_platform": {
            "osx_arm64": "osx_64",
        },
        "conda_forge_output_validation": True,
        "provider": {
            "linux_aarch64": "default",
            "linux_ppc64le": "default",
        },
        "test_on_native_only": True,
        "github": {
            "branch_name": "main",
            "tooling_branch_name": "main",
        },
        "idle_timeout_minutes": 60,
        "conda_build": {
            "pkg_format": "2",
        },
    },
]


@pytest.mark.parametrize("config_dict", SAMPLE_CONFIGS)
def test_config_model_validation(config_dict):
    config = ConfigModel(**config_dict)
    assert config  # Ensure the configuration is valid


# To be removed in future release
@pytest.fixture
def base_config_data():
    """
    As part of a legacy code overhaul, this fixture is used to compare the
    previous default config data with the current default config data that;s generated from the pydantic ConfigModel.
    """
    with open("conda_smithy/schema/conda-forge.defaults.yml") as forge:
        default_config_data = yaml.safe_load(forge)

    return default_config_data


def test_base_config(base_config_data):
    """
    This test compares the base config data yaml, by initializing a ConfigModel with the base config data.
    """
    ConfigModel(**base_config_data)


def test_validate_win_64_enabled():
    config_dict = {
        "win_64": {"enabled": False},
        "build_platform": {
            "win_64": "win_64",
        },
    }
    # validator should raise an error if win_64 is disabled
    pytest.raises(ValueError, ConfigModel, **config_dict)


def test_extra_fields():
    config_dict = {
        "extra_field": "extra_value",
        "github": {
            "branch_name": "main",
            "tooling_branch_name": "main",
        },
        "conda_forge_output_validation": True,
        "conda_build": {
            "pkg_format": "2",
        },
    }
    # Extra value should be ignored
    config = ConfigModel(**config_dict)
    # assert value is not present after dumping to dict
    assert "extra_field" not in config.model_dump()


def test_invalid_config():
    invalid_data = {
        "docker": {
            "executable": "docker",
            "fallback_image": 123,  # Invalid data, should be a string
            "command": "bash",
        },
        # Add other fields with invalid data here...
    }

    with pytest.raises(ValidationError):
        ConfigModel(**invalid_data)
