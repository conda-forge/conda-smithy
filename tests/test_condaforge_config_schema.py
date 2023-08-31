import pytest
from pydantic import ValidationError
from conda_smithy.schema.models import ConfigModel


# To be removed in future release
@pytest.fixture
def default_config_data():
    """
    As part of a legacy code overhaul, this fixture is used to compare the
    previous default config data with the current default config data that;s generated from the pydantic ConfigModel.
    """
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
            # default choices for MS-hosted agents
            "settings_linux": {
                "pool": {
                    "vmImage": "ubuntu-latest",
                },
                "timeoutInMinutes": 360,
            },
            "settings_osx": {
                "pool": {
                    "vmImage": "macOS-11",
                },
                "timeoutInMinutes": 360,
            },
            "settings_win": {
                "pool": {
                    "vmImage": "windows-2022",
                },
                "timeoutInMinutes": 360,
                "variables": {
                    "CONDA_BLD_PATH": r"D:\\bld\\",
                    # Custom %TEMP% for upload to avoid permission errors.
                    # See https://github.com/conda-forge/kubo-feedstock/issues/5#issuecomment-1335504503
                    "UPLOAD_TEMP": r"D:\\tmp",
                },
            },
            # Force building all supported providers.
            "force": False,
            # name and id of azure project that the build pipeline is in
            "project_name": "feedstock-builds",
            "project_id": "84710dde-1620-425b-80d0-4cf5baca359d",
            # Set timeout for all platforms at once.
            "timeout_minutes": None,
            # Toggle creating pipeline artifacts for conda build_artifacts dir
            "store_build_artifacts": False,
            # Maximum number of parallel jobs allowed across platforms
            "max_parallel": 50,
        },
        "provider": {
            "linux_64": ["azure"],
            "osx_64": ["azure"],
            "win_64": ["azure"],
            # Following platforms are disabled by default
            "linux_aarch64": None,
            "linux_ppc64le": None,
            "linux_armv7l": None,
            "linux_s390x": None,
            # Following platforms are aliases of x86_64,
            "linux": None,
            "osx": None,
            "win": None,
        },
        # value is the build_platform, key is the target_platform
        "build_platform": {
            "linux_64": "linux_64",
            "linux_aarch64": "linux_aarch64",
            "linux_ppc64le": "linux_ppc64le",
            "linux_s390x": "linux_s390x",
            "linux_armv7l": "linux_armv7l",
            "win_64": "win_64",
            "osx_64": "osx_64",
        },
        "noarch_platforms": ["linux_64"],
        "os_version": {
            "linux_64": None,
            "linux_aarch64": None,
            "linux_ppc64le": None,
            "linux_armv7l": None,
            "linux_s390x": None,
        },
        "test": None,
        # Following is deprecated
        "test_on_native_only": False,
        "choco": [],
        # Configurable idle timeout.  Used for packages that don't have chatty enough builds
        # Applicable only to circleci and travis
        "idle_timeout_minutes": None,
        # Compiler stack environment variable
        "compiler_stack": "comp7",
        # Stack variables,  These can be used to impose global defaults for how far we build out
        "min_py_ver": "27",
        "max_py_ver": "37",
        "min_r_ver": "34",
        "max_r_ver": "34",
        "channels": {
            "sources": ["conda-forge"],
            "targets": [["conda-forge", "main"]],
        },
        "github": {
            "user_or_org": "conda-forge",
            "repo_name": "",
            "branch_name": "main",
            "tooling_branch_name": "main",
        },
        "github_actions": {
            "self_hosted": False,
            # Set maximum parallel jobs
            "max_parallel": None,
            # Toggle creating artifacts for conda build_artifacts dir
            "store_build_artifacts": False,
            "artifact_retention_days": 14,
        },
        "recipe_dir": "recipe",
        "skip_render": [],
        "bot": {"automerge": False},
        "conda_forge_output_validation": False,
        "private_upload": False,
        "secrets": [],
        "build_with_mambabuild": True,
        # feedstock checkout git clone depth, None means keep default, 0 means no limit
        "clone_depth": None,
        # Specific channel for package can be given with
        #     ${url or channel_alias}::package_name
        # defaults to conda-forge channel_alias
        "remote_ci_setup": ["conda-forge-ci-setup=3"],
    }


def test_valid_config(default_config_data):
    config = ConfigModel()

    # for each key in both the default config and the valid config, check that the
    # default config has the same value as the valid config
    _dump_config = config.model_dump(exclude_none=True)
    # first assert that all keys are the same
    assert set(_dump_config.keys()) == set(default_config_data.keys())

    # then assert that all values are the same
    for key in _dump_config.keys():
        if isinstance(_dump_config[key], dict):
            # if the value is a dict, assert that all keys are the same
            assert set(_dump_config[key].keys()) == set(
                default_config_data[key].keys()
            )
            # then assert that all values are the same
            for subkey in _dump_config[key].keys():
                assert (
                    _dump_config[key][subkey]
                    == default_config_data[key][subkey]
                )
        else:
            print(f"type: {type(_dump_config[key])}")
            print(key, _dump_config[key], default_config_data[key])
            assert _dump_config[key] == default_config_data[key]


def test_invalid_config():
    invalid_data = {
        "docker": {
            "executable": "docker",
            "fallback_image": 123,  # Invalid data, should be a string
            "command": "bash",
        },
        # Add other fields with invalid data here...
    }
    try:
        c = ConfigModel(**invalid_data)
        raise AssertionError("Should have raised a ValidationError")
    except ValidationError as e:
        pass
