from enum import Enum
from typing import Dict, List, Optional, Union, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from typing_extensions import Annotated

from conda_smithy.schema.platforms import (
    Platforms,
    WinConfig,
    MacOsxConfig,
    LinuxConfig,
    Aarch64Config,
    Ppc64leConfig,
)
from conda_smithy.schema.providers import CIservices, AzureConfig, GithubConfig


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


class CondaBuildConfig(BaseModel):
    pkg_format: Union[int, str, None] = Field(
        description="The package format for conda build. This can be one of 1, 2, or tar. The default is 2.",
        default="2",
    )

    zstd_compression_level: int = Field(
        default=16,
        description="The compression level for the zstd compression algorithm for .conda artifacts. conda-forge uses a default value of 16 since its artifacts can be large.",
    )

    @field_validator("pkg_format")
    def pkg_format_validator(cls, v):
        if not v:
            return v

        valid_values = ["2", None]
        if v not in valid_values:
            raise ValueError(
                f"Invalid value {v} for pkg_format. Valid values are {valid_values}"
            )
        return v


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


class ShellCheck(BaseModel):
    enabled: bool = Field(
        description="Whether to use shellcheck to lint shell scripts",
        default=False,
    )


class ConfigModel(BaseModel):
    appveyor: Dict[str, Any] = Field(
        default={"image": "Visual Studio 2017"},
        description="AppVeyor CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    azure: AzureConfig = AzureConfig()

    bot: BotConfig = BotConfig()

    build_platform: Annotated[
        Union[Dict[Platforms, Platforms], None],
        Field(
            description="This is a mapping from the target platform to the build platform for the package to be built."
        ),
    ] = {p.value: p.value for p in Platforms}

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
    ] = None

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
    ] = GithubConfig(
        user_or_org="conda-forge",
        repo_name="",
        branch_name="main",
        tooling_branch_name="main",
    )

    idle_timeout_minutes: Annotated[
        Union[int, None],
        Field(
            description="Configurable idle timeout.  Used for packages that don't have chatty enough builds. Applicable only to circleci and travis"
        ),
    ] = None

    win: Annotated[
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
    ] = [Platforms.linux_64.value]

    os_version: Annotated[
        Union[Dict[Platforms, str], None],
        Field(
            description="This key is used to set the OS versions for linux_* platforms. Valid entries map a linux platform and arch to either cos6 or cos7. Currently cos6 is the default for linux-64. All other linux architectures use CentOS 7."
        ),
    ] = {p.value: None for p in Platforms if p.value.startswith("linux")}

    provider: Annotated[
        Union[
            Dict[Platforms, Union[List[CIservices], CIservices, bool, None]],
            None,
        ],
        Field(
            description="The provider field is a mapping from build platform (not target platform) to CI service. It determines which service handles each build platform. If a desired build platform is not available with a selected provider (either natively or with emulation), the build will be disabled. Use the build_platform field to manually specify cross-compilation when no providers offer a desired build platform."
        ),
    ] = {
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
    }

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
            ".github/workflows",
        ]
        for i in v:
            if i not in valid_values:
                raise ValueError(
                    f"Invalid value {i} for skip_render. Valid values are {valid_values}"
                )
        return v

    templates: Annotated[
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
    ] = False

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

    travis: Annotated[
        Union[Dict[str, Any], None],
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

    github_actions: Dict[str, Any] = Field(
        description="GitHub Actions CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
        default={
            "self_hosted": False,
            # Set maximum parallel jobs
            "max_parallel": None,
            # Toggle creating artifacts for conda build_artifacts dir
            "store_build_artifacts": False,
            "artifact_retention_days": 14,
        },
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

    timeout_minutes: int = Field(
        default=None,
        description="The timeout in minutes for all platforms",
    )
