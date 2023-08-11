import json
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from typing_extensions import Annotated


class Platforms(str, Enum):
    linux_64 = "linux_64"
    linux_aarch64 = "linux_aarch64"
    linux_ppc64le = "linux_ppc64le"
    linux_armv7l = "linux_armv7l"
    linux_s390x = "linux_s390x"
    win_64 = "win_64"
    osx_64 = "osx_64"
    osx_arm64 = "osx_arm64"

    @classmethod
    @model_validator(mode="before")
    def check_platforms(cls, values):
        if not values:
            return values

        # Check that the build platforms are valid
        for k, v in values.items():
            # key and value must comply with <platform>_<arch> format
            try:
                build_platform = k.split("_")[0]
                target_platform = v.split("_")[0]
            except IndexError:
                raise ValueError(
                    f"Build platform {k} and target platform {v} must comply with <platform>_<arch> format"
                )
            return values


# class BuildPlatforms(BaseModel):
#     """
#     This is a list of the supported build platforms for the conda-forge CI.
#     """

#     model_config = ConfigDict(extra="allow")

#     linux_64: str = "linux_64"
#     linux_aarch64: str = "linux_aarch64"
#     linux_ppc64le: str = "linux_ppc64le"
#     linux_armv7l: str = "linux_armv7l"
#     linux_s390x: str = "linux_s390x"
#     win_64: str = "win_64"
#     osx_64: str = "osx_64"
#     # osx_arm64 = "osx_arm64" Not supported yet

#     @model_validator(mode="before")
#     @classmethod
#     def check_build_platforms(cls, values):
#         if not values:
#             return values

#         # Check that the build platforms are valid
#         for k, v in values.items():
#             # key and value must comply with <platform>_<arch> format
#             try:
#                 build_platform = k.split("_")[0]
#                 target_platform = v.split("_")[0]
#             except IndexError:
#                 raise ValueError(
#                     f"Build platform {k} and target platform {v} must comply with <platform>_<arch> format"
#                 )
#             if build_platform != target_platform:
#                 raise ValueError(
#                     f"Build platform {build_platform} must match target platform {target_platform}"
#                 )
#             return values


class AzureSelfHostedRunnerSettings(BaseModel):
    """This is the settings for self-hosted runners."""

    pool: Dict[str, str] = Field(
        description="The pool of self-hosted runners, e.g. 'vmImage': 'ubuntu-latest'"
    )
    timeoutInMinutes: int = Field(
        default=360, description="Timeout in minutes"
    )
    variables: Optional[Dict[str, str]] = Field(
        default=None, description="Variables"
    )


class AzureConfig(BaseModel):
    """
    This dictates the behavior of the Azure Pipelines CI service. It is a mapping for Azure-specific configuration options. For more information, see the [Azure Pipelines schema reference documentation](https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/?view=azure-pipelines).
    """

    project_name: str = Field(
        default="feedstock-builds",
        description="The name of the Azure Pipelines project",
    )

    project_id: str = Field(
        default="84710dde-1620-425b-80d0-4cf5baca359d",  # shouldn't this be an environment variable?
        description="The ID of the Azure Pipelines project",
    )

    timeout_minutes: Annotated[
        Union[int, None],
        Field(
            description="The maximum amount of time (in minutes) that a job can run before it is automatically canceled"
        ),
    ] = None

    # flag for forcing the building all supported providers
    force: Annotated[
        Union[bool, None],
        Field(description="Force building all supported providers"),
    ] = False

    # toggle for storing the conda build_artifacts directory (including the
    # built packages) as an Azure pipeline artifact that can be downloaded
    store_build_artifacts: Annotated[
        Union[bool, None],
        Field(
            description="Store the conda build_artifacts directory as an Azure pipeline artifact"
        ),
    ] = False

    # toggle for freeing up some extra space on the default Azure Pipelines
    # linux image before running the Docker container for building
    free_disk_space: Annotated[
        Union[bool, None], Field(description="Free up disk space")
    ] = None

    # limit the amount of CI jobs running concurrently at a given time
    # each OS will get its proportional share of the configured value
    max_parallel: Annotated[
        Union[int, None], Field(description="Maximum number of parallel jobs")
    ] = 50

    # Self-hosted runners specific configuration
    settings_linux: AzureSelfHostedRunnerSettings = Field(
        default=AzureSelfHostedRunnerSettings(
            pool={"vmImage": "ubuntu-latest"}, timeoutInMinutes=360
        ),
        description="Linux-specific settings for self-hosted runners",
    )

    settings_osx: AzureSelfHostedRunnerSettings = Field(
        default=AzureSelfHostedRunnerSettings(
            pool={"vmImage": "macOS-11"}, timeoutInMinutes=360
        ),
        description="OSX-specific settings for self-hosted runners",
    )

    settings_win: AzureSelfHostedRunnerSettings = Field(
        default=AzureSelfHostedRunnerSettings(
            pool={"vmImage": "windows-2022"},
            timeoutInMinutes=360,
            variables={
                "CONDA_BLD_PATH": r"D:\\bld\\",
                "UPLOAD_TEMP": r"D:\\tmp",
            },
        ),
        description="Windows-specific settings for self-hosted runners",
    )


class BotConfigAutoMergeChoice(str, Enum):
    VERSION = "version"
    MIGRATION = "migration"


class BotConfigInspectionChoice(str, Enum):
    HINT = "hint"
    HINT_ALL = "hint-all"
    HINT_SOURCE = "hint-source"
    HINT_GRAYSKULL = "hint-grayskull"
    UPDATE_ALL = "update-all"
    UPDATE_SOURCE = "update-source"
    UPDATE_GRAYSKULL = "update-grayskull"


class BotConfig(BaseModel):
    """This dictates the behavior of the conda-forge auto-tick bot which issues automatic version updates/migrations for feedstocks."""

    automerge: Annotated[
        Union[bool, BotConfigAutoMergeChoice],
        Field(description="Automatically merge PRs if possible"),
    ] = False

    check_solvable: Annotated[
        Union[bool, None],
        Field(
            description="Open PRs only if resulting environment is solvable."
        ),
    ] = None

    inspection: Annotated[
        Union[BotConfigInspectionChoice, None],
        Field(
            description="Method for generating hints or updating recipe",
        ),
    ] = None

    abi_migration_branches: Annotated[
        Union[List[str], None],
        Field(description="List of branches for additional bot migration PRs"),
    ] = None

    version_updates_random_fraction_to_keep: Annotated[
        Union[float, None],
        Field(
            description="Fraction of versions to keep for frequently updated packages"
        ),
    ] = None


class ChannelPriorityConfig(str, Enum):
    STRICT = "strict"
    FLEXIBLE = "flexible"
    DISABLED = "disabled"


class CondaForgeChannels(BaseModel):
    """This represents the channels to grab packages from during builds and which channels/labels to push to on anaconda.org after a package has been built. The channels variable is a mapping with sources and targets."""

    sources: List[str] = Field(
        default=["conda-forge"],
        description="sources selects the channels to pull packages from, in order",
    )

    targets: List[List[str]] = Field(
        default=[["conda-forge", "main"]],
        description="targets is a list of 2-lists, where the first element is the channel to push to and the second element is the label on that channel",
    )


class CondaBuildPackageFormats(str, Enum):
    conda: int = 2  # makes .conda artifacts
    tar: Union[int, None] = None  # makes .tar.bz2 artifacts


class CondaBuildConfig(BaseModel):
    pkg_format: CondaBuildPackageFormats = CondaBuildPackageFormats.conda
    zstd_compression_level: int = Field(
        default=16,
        description="The compression level for the zstd compression algorithm for .conda artifacts. conda-forge uses a default value of 16 since its artifacts can be large.",
    )


class CondaForgeDocker(BaseModel):
    model_config = ConfigDict(extra="allow")

    executable: str = Field(
        description="The executable for Docker", default="docker"
    )

    fallback_image: str = Field(
        description="The fallback image for Docker",
        default="quay.io/condaforge/linux-anvil-comp7",
    )

    command: str = Field(
        description="The command to run in Docker", default="bash"
    )

    interactive: bool = Field(
        description="Whether to run Docker in interactive mode", default=None
    )

    image: str = Field(description="The image for Docker", default=None)


class MacOsxConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra macOSX-specific configuration options",
        default=False,
    )


class WinConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra Windows-specific configuration options",
        default=False,
    )


class LinuxConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra Linux-specific configuration options",
        default=False,
    )


class Aarch64Config(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra ARM-specific configuration options",
        default=False,
    )


class Ppc64leConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra PPC-specific configuration options",
        default=False,
    )


class ShellCheck(BaseModel):
    enabled: bool = Field(
        description="Whether to use shellcheck to lint shell scripts",
        default=False,
    )


class GithubConfig(BaseModel):
    user_or_org: str = Field(
        description="The name of the GitHub organization",
        default="conda-forge",
    )
    repo_name: str = Field(
        description="The name of the repository",
        default="",
    )
    branch_name: str = Field(
        description="The name of the branch to execute on",
        default="main",
    )
    tooling_branch_name: str = Field(
        description="The name of the branch to use for rerender+webservices github actions and conda-forge-ci-setup-feedstock references",
        default="main",
    )


class CIservices(str, Enum):
    azure = "azure"
    circle = "circle"
    travis = "travis"
    appveyor = "appveyor"
    default = "default"


class ConfigModel(BaseModel):
    appveyor: Dict[str, str] = Field(
        default={"image": "Visual Studio 2017"},
        description="AppVeyor CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    azure: AzureConfig = AzureConfig()

    bot: BotConfig = BotConfig()

    build_platforms: Annotated[
        Union[Dict[Platforms, Platforms], None],
        Field(
            description="This is a mapping from the target platform to the build platform for the package to be built."
        ),
    ] = {p: p for p in Platforms}

    build_with_mambabuild: Annotated[
        Union[bool, None],
        Field(
            description="configures the conda-forge CI to run a debug build using the mamba solver. More information can be in the [mamba docs](https://conda-forge.org/docs/maintainer/maintainer_faq.html#mfaq-mamba-local)."
        ),
    ] = True

    channel_priority: Annotated[
        Union[ChannelPriorityConfig, None],
        Field(
            description="The channel priority level for the conda solver during feedstock builds. This can be one of `strict`, `flexible`, or `disabled`. For more information, see the [Strict channel priority](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-channels.html#strict-channel-priority) section on conda documentation."
        ),
    ] = "strict"

    channels: CondaForgeChannels = CondaForgeChannels()

    choco: Annotated[
        Union[List[str], None],
        Field(
            description="This parameter allows for conda-smithy to run chocoloatey installs on Windows when additional system packages are needed. This is a list of strings that represent package names and any additional parameters."
        ),
    ] = []

    circle: Dict[str, str] = Field(
        default={},
        description="Circle CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    conda_build: Annotated[
        Union[CondaBuildConfig, None],
        Field(
            description="Settings in this block are used to control how conda build runs and produces artifacts."
        ),
    ] = None

    conda_forge_output_validation: Annotated[
        Union[bool, None],
        Field(
            description="This field must be set to True for feedstocks in the conda-forge GitHub organization. It enables the required feedstock artifact validation as described in [Output Validation and Feedstock Tokens](https://conda-forge.org/docs/maintainer/infrastructure.html#output-validation)."
        ),
    ] = False

    docker: Annotated[
        Union[CondaForgeDocker, None],
        Field(
            description="This is a mapping for Docker-specific configuration options."
        ),
    ] = CondaForgeDocker()

    github: Annotated[
        Union[GithubConfig, None],
        Field(
            description="Mapping for GitHub-specific configuration options",
        ),
    ] = None

    idle_timeout_minutes: Annotated[
        Union[int, None],
        Field(
            description="Configurable idle timeout.  Used for packages that don't have chatty enough builds. Applicable only to circleci and travis"
        ),
    ] = None

    win = Annotated[
        Union[WinConfig, None],
        Field(
            description="Windows-specific configuration options. This is largely an internal setting and should not normally be manually modified."
        ),
    ] = None

    osx: Annotated[
        Union[MacOsxConfig, None],
        Field(
            description="OSX-specific configuration options. This is largely an internal setting and should not normally be manually modified."
        ),
    ] = None

    linux: Annotated[
        Union[LinuxConfig, None],
        Field(
            description="Linux-specific configuration options. This is largely an internal setting and should not normally be manually modified."
        ),
    ] = None

    linux_aarch64: Annotated[
        Union[Aarch64Config, None],
        Field(
            description="ARM-specific configuration options. This is largely an internal setting and should not normally be manually modified."
        ),
    ] = None

    linux_ppc64le: Annotated[
        Union[Ppc64leConfig, None],
        Field(
            description="PPC-specific configuration options. This is largely an internal setting and should not normally be manually modified."
        ),
    ] = None

    noarch_platforms: Annotated[
        Union[List[Platforms], None],
        Field(
            description="Platforms on which to build noarch packages. The preferred default is a single build on linux_64."
        ),
    ] = [Platforms.linux_64]

    os_version: Annotated[
        Union[Dict[Platforms, str], None],
        Field(
            description="This key is used to set the OS versions for linux_* platforms. Valid entries map a linux platform and arch to either cos6 or cos7. Currently cos6 is the default for linux-64. All other linux architectures use CentOS 7."
        ),
    ] = {p: None for p in Platforms if p.value.startswith("linux")}

    provider = Annotated[
        Union[Dict[Platforms, Union[List[CIservices], bool, None]], None],
        Field(
            description="The provider field is a mapping from build platform (not target platform) to CI service. It determines which service handles each build platform. If a desired build platform is not available with a selected provider (either natively or with emulation), the build will be disabled. Use the build_platform field to manually specify cross-compilation when no providers offer a desired build platform."
        ),
    ] = (
        {
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
    )

    recipe_dir: str = Field(
        description="The relative path to the recipe directory",
        default="recipe",
    )

    remote_ci_setup: Annotated[
        Union[List[str], None],
        Field(
            description="This option can be used to override the default conda-forge-ci-setup package. Can be given with ${url or channel_alias}::package_name, defaults to conda-forge channel_alias if no prefix is given."
        ),
    ] = ["conda-forge-ci-setup=3"]

    shellcheck: Annotated[
        Union[ShellCheck, None],
        Field(
            description="Shell scripts used for builds or activation scripts can be linted with shellcheck. This option can be used to enable shellcheck and configure its behavior."
        ),
    ] = None

    skip_render: Annotated[
        Union[List[str], None],
        Field(
            description="This option specifies a list of files which conda smithy will skip rendering. The possible values can be a subset of .gitignore, .gitattributes, README.md, LICENSE.txt. The default value is an empty list [ ]"
        ),
    ] = []

    @field_validator("skip_render")
    def skip_render_validator(cls, v):
        if not v:
            return v

        valid_values = [
            ".gitignore",
            ".gitattributes",
            "README.md",
            "LICENSE.txt",
        ]
        for i in v:
            if i not in valid_values:
                raise ValueError(
                    f"Invalid value {i} for skip_render. Valid values are {valid_values}"
                )
        return v

    templates = Annotated[
        Union[Dict[str, str], None],
        Field(
            description="This is mostly an internal field for specifying where templates files live. You shouldn't need it."
        ),
    ] = {}

    test_on_native_only: Annotated[
        Union[bool, None],
        Field(
            description="This is used for disabling testing for cross compiling. Default is false. This has been deprecated in favor of the test top-level field. It is now mapped to test: native_and_emulated."
        ),
    ] = None

    test: Annotated[
        Union[str, None],
        Field(
            description="This is used to configure on which platforms a recipe is tested. Default is all. Valid values are all, native_only, native_and_emulated, and emulated_only."
        ),
    ] = None

    @field_validator("test")
    def test_validator(cls, v):
        if not v:
            return v

        valid_values = [
            "all",
            "native_only",
            "native_and_emulated",
            "emulated_only",
        ]
        if v not in valid_values:
            raise ValueError(
                f"Invalid value {v} for test. Valid values are {valid_values}"
            )
        return v

    travis = Annotated[
        Union[Dict[str, str], None],
        Field(
            description="Travis CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed."
        ),
    ] = {}

    upload_on_branch: Annotated[
        Union[str, None],
        Field(
            description="This parameter restricts uploading access on work from certain branches of the same repo. Only the branch listed in upload_on_branch will trigger uploading of packages to the target channel. The default is to skip this check if the key upload_on_branch is not in conda-forge.yml"
        ),
    ] = None

    drone: Dict[str, str] = Field(
        default={},
        description="Drone CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    woodpecker: Dict[str, str] = Field(
        default={},
        description="Woodpecker CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    config_version: str = Field(
        default="2",
        description="The version of the conda-forge.yml specification. This should not be manually modified.",
    )

    compiler_stack: str = Field(
        default="comp7",
        description="Compiler stack environment variable",
    )

    min_py_ver: str = Field(
        default="27",
        description="Minimum Python version",
    )
    max_py_ver: str = Field(
        default="37",
        description="Maximum Python version",
    )
    min_r_ver: str = Field(
        default="34",
        description="Minimum R version",
    )
    max_r_ver: str = Field(
        default="34",
        description="Maximum R version",
    )
    github_actions: Dict[str, bool] = Field(
        default={},
        description="GitHub Actions CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )
    private_upload: bool = Field(
        default=False,
        description="Whether to upload to a private channel",
    )
    secrets: List[str] = Field(
        default=[],
        description="List of secrets to be used in GitHub Actions",
    )
    clone_depth: Optional[int] = Field(
        default=None,
        description="The depth of the git clone",
    )
    remote_ci_setup: List[str] = Field(
        default=["conda-forge-ci-setup=3"],
        description="This option can be used to override the default conda-forge-ci-setup package. Can be given with ${url or channel_alias}::package_name, defaults to conda-forge channel_alias if no prefix is given.",
    )

    # class Config:
    #     # This allows Pydantic to use the default values from the model if the key is missing in the input dictionary.
    #     extra = "allow" -- Deprecated use ConfigDict instead


if __name__ == "__main__":
    # Create a config object from the model
    config = ConfigModel()
    # Print the config object as a dictionary
    print(config.model_dump())

    # Print the config object (exclude_none=True) as a JSON string with indents and sorted keys
    print(config.model_dump_json(exclude_none=True, indent=2))

    _config = {
        "docker": {
            "executable": "docker",
            "fallback_image": "quay.io/condaforge/linux-anvil-comp7",
            "command": "bash",
        },
        # "templates": {},
        # "drone": {},
        # "woodpecker": {},
        # "travis": {},
        "circle": {},
        # "config_version": "2",
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
            # "timeout_minutes": None,
            # Toggle creating pipeline artifacts for conda build_artifacts dir
            "store_build_artifacts": False,
            # Maximum number of parallel jobs allowed across platforms
            "max_parallel": 50,
        },
        # "provider": {
        #     "linux_64": ["azure"],
        #     "osx_64": ["azure"],
        #     "win_64": ["azure"],
        #     # Following platforms are disabled by default
        #     "linux_aarch64": None,
        #     "linux_ppc64le": None,
        #     "linux_armv7l": None,
        #     "linux_s390x": None,
        #     # Following platforms are aliases of x86_64,
        #     "linux": None,
        #     "osx": None,
        #     "win": None,
        # },
        # # value is the build_platform, key is the target_platform
        "build_platform": {
            "linux_64": "linux_64",
            "linux_aarch64": "linux_aarch64",
            "linux_ppc64le": "linux_ppc64le",
            "linux_s390x": "linux_s390x",
            "linux_armv7l": "linux_armv7l",
            "win_64": "win_64",
            "osx_64": "osx_64",
            # "osx_arm64": "osx_arm64",  # TODO: Check with Jaime if this is expected
        },
        # "noarch_platforms": ["linux_64"],
        # "os_version": {
        #     "linux_64": None,
        #     "linux_aarch64": None,
        #     "linux_ppc64le": None,
        #     "linux_armv7l": None,
        #     "linux_s390x": None,
        # },
        # "test": None,
        # # Following is deprecated
        # "test_on_native_only": False,
        "choco": [],
        # # Configurable idle timeout.  Used for packages that don't have chatty enough builds
        # # Applicable only to circleci and travis
        # "idle_timeout_minutes": None,
        # # Compiler stack environment variable
        # "compiler_stack": "comp7",
        # # Stack variables,  These can be used to impose global defaults for how far we build out
        # "min_py_ver": "27",
        # "max_py_ver": "37",
        # "min_r_ver": "34",
        # "max_r_ver": "34",
        "channels": {
            "sources": ["conda-forge"],
            "targets": [["conda-forge", "main"]],
        },
        # "github": {
        #     "user_or_org": "conda-forge",
        #     "repo_name": "",
        #     "branch_name": "main",
        #     "tooling_branch_name": "main",
        # },
        # "github_actions": {
        #     "self_hosted": False,
        #     # Set maximum parallel jobs
        #     "max_parallel": None,
        #     # Toggle creating artifacts for conda build_artifacts dir
        #     "store_build_artifacts": False,
        #     "artifact_retention_days": 14,
        # },
        # "recipe_dir": "recipe",
        # "skip_render": [],
        "bot": {"automerge": False},
        "conda_forge_output_validation": False,
        # "private_upload": False,
        # "secrets": [],
        # "build_with_mambabuild": True,
        # # feedstock checkout git clone depth, None means keep default, 0 means no limit
        # "clone_depth": None,
        # # Specific channel for package can be given with
        # #     ${url or channel_alias}::package_name
        # # defaults to conda-forge channel_alias
        # "remote_ci_setup": ["conda-forge-ci-setup=3"],
    }

    # c = config.model_dump(exclude_none=True)
    # assert c.keys() == _config.keys()
    # for k, v in c.items():
    #     if isinstance(v, dict):
    #         print(f"Model config: {v.keys()}")
    #         print(f"Loaded config: {_config[k].keys()}")

    #         try:
    #             if len(v.keys()) != len(_config[k].keys()):
    #                 raise AssertionError(
    #                     f"Length of keys don't match: {len(v.keys())} != {len(_config[k].keys())}"
    #                 )
    #             assert v.keys() == _config[k].keys()
    #         except AssertionError:
    #             # identify the missing keys
    #             print(
    #                 f"Missing keys: {set(v.keys()) - set(_config[k].keys())}"
    #             )
    #         except Exception as e:
    #             raise e

    #         for k2, v2 in v.items():
    #             assert v2 == _config[k][k2]
    #     else:
    #         assert v == _config[k]
