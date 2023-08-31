from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from conda_smithy.schema.platforms import (
    Aarch64Config,
    LinuxConfig,
    MacOsxConfig,
    Platforms,
    Ppc64leConfig,
    WinConfig,
)
from conda_smithy.schema.providers import AzureConfig, CIservices, GithubConfig


class BotConfigAutoMergeChoice(str, Enum):
    VERSION = "version"
    MIGRATION = "migration"


class BotConfigSkipRenderChoices(str, Enum):
    GITIGNORE = ".gitignore"
    GITATTRIBUTES = ".gitattributes"
    README = "README.md"
    LICENSE = "LICENSE.txt"
    GITHUB_WORKFLOWS = ".github/workflows"


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

    automerge: Union[bool, BotConfigAutoMergeChoice] = Field(
        False,
        description="Automatically merge PRs if possible",
    )

    check_solvable: bool = Field(
        False,
        description="Open PRs only if resulting environment is solvable.",
    )

    inspection: Union[BotConfigInspectionChoice, None] = Field(
        None,
        description="Method for generating hints or updating recipe",
    )

    abi_migration_branches: Union[List[str], None] = Field(
        None,
        description="List of branches for additional bot migration PRs",
    )

    version_updates_random_fraction_to_keep: Union[float, None] = Field(
        None,
        description="Fraction of versions to keep for frequently updated packages",
    )


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
    pkg_format: Literal["1", "2", "tar"] = Field(
        description="The package version format for conda build. This can be either '1', '2', or 'tar'. The default is '2'.",
        default="2",
    )

    zstd_compression_level: int = Field(
        default=16,
        description="The compression level for the zstd compression algorithm for .conda artifacts. conda-forge uses a default value of 16 for a good compromise of performance and compression.",
    )


class CondaForgeDocker(BaseModel):
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
        description="Whether to run Docker in interactive mode", default=False
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

    azure: AzureConfig

    bot: BotConfig

    build_platform: Union[Dict[Platforms, Platforms], None] = Field(
        ...,
        description="This is a mapping from the target platform to the build platform for the package to be built.",
    )

    build_with_mambabuild: bool = Field(
        default=True,
        description="configures the conda-forge CI to run a debug build using the mamba solver. More information can be in the [mamba docs](https://conda-forge.org/docs/maintainer/maintainer_faq.html#mfaq-mamba-local).",
    )

    channel_priority: Optional[ChannelPriorityConfig] = Field(
        default=None,
        description="The channel priority level for the conda solver during feedstock builds. This can be one of `strict`, `flexible`, or `disabled`. For more information, see the [Strict channel priority](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-channels.html#strict-channel-priority) section on conda documentation.",
    )

    channels: CondaForgeChannels()

    choco: List[str] = Field(
        default_factory=list,
        description="This parameter allows for conda-smithy to run chocoloatey installs on Windows when additional system packages are needed. This is a list of strings that represent package names and any additional parameters.",
    )

    circle: Dict[str, Any] = Field(
        default_factory=dict,
        description="Circle CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    conda_build: Optional[CondaBuildConfig] = Field(
        default=None,
        description="Settings in this block are used to control how conda build runs and produces artifacts.",
    )

    conda_forge_output_validation: bool = Field(
        default=False,
        description="This field must be set to True for feedstocks in the conda-forge GitHub organization. It enables the required feedstock artifact validation as described in [Output Validation and Feedstock Tokens](https://conda-forge.org/docs/maintainer/infrastructure.html#output-validation).",
    )

    docker: Optional[CondaForgeDocker] = Field(
        ...,
        description="This is a mapping for Docker-specific configuration options.",
    )

    github: Optional[GithubConfig] = Field(
        ...,
        description="Mapping for GitHub-specific configuration options",
    )

    idle_timeout_minutes: Optional[int] = Field(
        default=None,
        description="Configurable idle timeout.  Used for packages that don't have chatty enough builds. Applicable only to circleci and travis",
    )

    win: Optional[WinConfig] = Field(
        default=None,
        description="Windows-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    osx: Optional[MacOsxConfig] = Field(
        default=None,
        description="OSX-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    linux: Optional[LinuxConfig] = Field(
        default=None,
        description="Linux-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    linux_aarch64: Optional[Aarch64Config] = Field(
        default=None,
        description="ARM-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    linux_ppc64le: Optional[Ppc64leConfig] = Field(
        default=None,
        description="PPC-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    noarch_platforms: List[Platforms] = Field(
        default_factory=lambda: ["linux_64"],
        description="Platforms on which to build noarch packages. The preferred default is a single build on linux_64.",
    )

    os_version: Dict[Platforms, Optional[str]] = Field(
        default_factory=lambda: {
            p: None
            for p in Platforms().model_dump().keys()
            if p.startswith("linux")
        },
        description="This key is used to set the OS versions for linux_* platforms. Valid entries map a linux platform and arch to either cos6 or cos7. Currently cos6 is the default for linux-64. All other linux architectures use CentOS 7.",
    )

    provider: Dict[
        Platforms, Union[List[CIservices], CIservices, bool, None]
    ] = Field(
        ...,
        description="The provider field is a mapping from build platform (not target platform) to CI service. It determines which service handles each build platform. If a desired build platform is not available with a selected provider (either natively or with emulation), the build will be disabled. Use the build_platform field to manually specify cross-compilation when no providers offer a desired build platform.",
    )

    recipe_dir: str = Field(
        default="recipe",
        description="The relative path to the recipe directory",
    )

    remote_ci_setup: List[str] = Field(
        default_factory=lambda: ["conda-forge-ci-setup=3"],
        description="This option can be used to override the default conda-forge-ci-setup package. Can be given with ${url or channel_alias}::package_name, defaults to conda-forge channel_alias if no prefix is given.",
    )

    shellcheck: Optional[ShellCheck] = Field(
        default=None,
        description="Shell scripts used for builds or activation scripts can be linted with shellcheck. This option can be used to enable shellcheck and configure its behavior.",
    )

    skip_render: List[BotConfigSkipRenderChoices] = Field(
        default_factory=list,
        description="This option specifies a list of files which conda smithy will skip rendering.",
    )

    templates: Dict[str, str] = Field(
        default_factory=dict,
        description="This is mostly an internal field for specifying where templates files live. You shouldn't need it.",
    )

    test_on_native_only: bool = Field(
        default=False,
        description="This is used for disabling testing for cross compiling. Default is false. This has been deprecated in favor of the test top-level field. It is now mapped to test: native_and_emulated.",
    )

    test: Optional[
        Literal["all", "native_only", "native_and_emulated", "emulated_only"]
    ] = Field(
        default=None,
        description="This is used to configure on which platforms a recipe is tested. Default is all. ",
    )

    travis: Dict[str, Any] = Field(
        default_factory=dict,
        description="Travis CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    upload_on_branch: Optional[str] = Field(
        default=None,
        description="This parameter restricts uploading access on work from certain branches of the same repo. Only the branch listed in upload_on_branch will trigger uploading of packages to the target channel. The default is to skip this check if the key upload_on_branch is not in conda-forge.yml",
    )

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
