import pytest
from pydantic import ValidationError
from conda_smithy.schema.models import ConfigModel


@pytest.fixture
def valid_config_data():
    return {
        "docker": {
            "executable": "docker",
            "fallback_image": "quay.io/condaforge/linux-anvil-comp7",
            "command": "bash",
        },
        "templates": {},
        "drone": {},
        "woodpecker": {},
        "travis": {},
        "circle": {},
        "config_version": "2",
        "appveyor": {"image": "Visual Studio 2017"},
        "azure": {
            # ... (Azure configuration data) ...
        },
        "provider": {
            # ... (Provider configuration data) ...
        },
        "build_platform": {
            # ... (Build platform configuration data) ...
        },
        "noarch_platforms": ["linux_64"],
        "os_version": {
            # ... (OS version configuration data) ...
        },
        "test": None,
        "test_on_native_only": False,
        "choco": [],
        "idle_timeout_minutes": None,
        "compiler_stack": "comp7",
        "min_py_ver": "27",
        "max_py_ver": "37",
        "min_r_ver": "34",
        "max_r_ver": "34",
        "channels": {
            # ... (Channels configuration data) ...
        },
        "github": {
            # ... (GitHub configuration data) ...
        },
        "github_actions": {
            # ... (GitHub Actions configuration data) ...
        },
        "recipe_dir": "recipe",
        "skip_render": [],
        "bot": {"automerge": False},
        "conda_forge_output_validation": False,
        "private_upload": False,
        "secrets": [],
        "build_with_mambabuild": True,
        "clone_depth": None,
        "remote_ci_setup": ["conda-forge-ci-setup=3"],
    }


# def test_valid_config(valid_config_data):
#     config = ConfigModel(**valid_config_data)
#     assert isinstance(config, ConfigModel)


@pytest.mark.xfail(raises=ValidationError)
def test_invalid_config():
    invalid_data = {
        "docker": {
            "executable": "docker",
            "fallback_image": 123,  # Invalid data, should be a string
            "command": "bash",
        },
        # Add other fields with invalid data here...
    }

    ConfigModel(**invalid_data)
