import pytest
from pydantic import ValidationError

from conda_smithy.schema import ConfigModel

# Sample config files
SAMPLE_CONFIGS = [
    {
        "github": {
            "branch_name": "main",
            "tooling_branch_name": "main",
        },
        "conda_forge_output_validation": True,
        "conda_build": {
            "pkg_format": 2,
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
            "pkg_format": 2,
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
            "pkg_format": 2,
        },
    },
]


@pytest.mark.parametrize("config_dict", SAMPLE_CONFIGS)
def test_config_model_validation(config_dict):
    config = ConfigModel(**config_dict)
    assert config  # Ensure the configuration is valid


def test_class_init():
    config = ConfigModel()
    assert config


def test_extra_fields():
    config_dict = {
        "extra_field": "extra_value",
        "github": {
            "branch_name": "main",
            "tooling_branch_name": "main",
        },
        "conda_forge_output_validation": True,
        "conda_build": {
            "pkg_format": 2,
        },
    }
    with pytest.raises(ValidationError):
        config = ConfigModel(**config_dict)
