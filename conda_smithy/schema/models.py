from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    FieldValidationInfo,
    field_validator,
)

from conda_smithy.schema.platforms import Platforms, PlatformUniqueConfig
from conda_smithy.schema.providers import AzureConfig, CIservices, GithubConfig


def sanitize_remote_ci_setup(package: str) -> str:
    if package.startswith(("'", '"')):
        return package
    elif ("<" in package) or (">" in package) or ("|" in package):
        return '"' + package + '"'
    return package


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

    automerge: Optional[Union[bool, BotConfigAutoMergeChoice]] = Field(
        False,
        description="Automatically merge PRs if possible",
    )

    check_solvable: Optional[bool] = Field(
        False,
        description="Open PRs only if resulting environment is solvable.",
    )

    inspection: Optional[BotConfigInspectionChoice] = Field(
        None,
        description="Method for generating hints or updating recipe",
    )

    abi_migration_branches: Optional[List[str]] = Field(
        None,
        description="List of branches for additional bot migration PRs",
    )

    version_updates_random_fraction_to_keep: Optional[float] = Field(
        None,
        description="Fraction of versions to keep for frequently updated packages",
    )


class ChannelPriorityConfig(str, Enum):
    STRICT = "strict"
    FLEXIBLE = "flexible"
    DISABLED = "disabled"


class CondaForgeChannels(BaseModel):
    """This represents the channels to grab packages from during builds and which channels/labels to push to on anaconda.org after a package has been built. The channels variable is a mapping with sources and targets."""

    sources: Optional[List[str]] = Field(
        default=["conda-forge"],
        description="sources selects the channels to pull packages from, in order",
    )

    targets: Optional[List[List[str]]] = Field(
        default=[["conda-forge", "main"]],
        description="targets is a list of 2-lists, where the first element is the channel to push to and the second element is the label on that channel",
    )


class CondaBuildConfig(BaseModel):
    pkg_format: Optional[Literal["1", "2", "tar"]] = Field(
        description="The package version format for conda build. This can be either '1', '2', or 'tar'. The default is '2'.",
        default="2",
    )

    zstd_compression_level: Optional[int] = Field(
        default=16,
        description="The compression level for the zstd compression algorithm for .conda artifacts. conda-forge uses a default value of 16 for a good compromise of performance and compression.",
    )

    error_overlinking: Optional[bool] = Field(
        default=False,
        description="Enable error when shared libraries from transitive  dependencies are  directly  linked  to any executables or shared libraries in  built packages. This is disabled by default. For more details, see the [conda build documentation](https://docs.conda.io/projects/conda-build/en/stable/resources/commands/conda-build.html).",
    )


class CondaForgeDocker(BaseModel):
    executable: Optional[str] = Field(
        description="The executable for Docker", default="docker"
    )

    fallback_image: Optional[str] = Field(
        description="The fallback image for Docker",
        default="quay.io/condaforge/linux-anvil-comp7",
    )

    command: Optional[str] = Field(
        description="The command to run in Docker", default="bash"
    )

    interactive: Optional[bool] = Field(
        description="Whether to run Docker in interactive mode",
        default=False,
        exclude=True,
    )

    # Deprecated values, if passed should raise errors
    image: Optional[Union[str, None]] = Field(
        description="Setting the Docker image in conda-forge.yml is no longer supported, use conda_build_config.yaml to specify Docker images.",
        default=None,
        exclude=True,
    )

    @field_validator("image", mode="before")
    def image_deprecated(cls, v):
        if v is not None:
            raise ValueError(
                "Setting the Docker image in conda-forge.yml is no longer supported."
                " Please use conda_build_config.yaml to specify Docker images."
            )
        return v


class ShellCheck(BaseModel):
    enabled: bool = Field(
        description="Whether to use shellcheck to lint shell scripts",
        default=False,
    )


class ConfigModel(BaseModel):
    # Values which are not expected to be present in the model dump, are flagged with exclude=True. This is to avoid confusion when comparing the model dump with the default conda-forge.yml file used for smithy or to avoid deprecated values been rendered.

    conda_build: Optional[CondaBuildConfig] = Field(
        default_factory=lambda: CondaBuildConfig(),
        description="Settings in this block are used to control how conda build runs and produces artifacts.",
    )

    conda_forge_output_validation: Optional[bool] = Field(
        default=True,
        description="This field must be set to True for feedstocks in the conda-forge GitHub organization. It enables the required feedstock artifact validation as described in [Output Validation and Feedstock Tokens](https://conda-forge.org/docs/maintainer/infrastructure.html#output-validation).",
    )

    github: Optional[GithubConfig] = Field(
        default_factory=lambda: GithubConfig(),
        description="Mapping for GitHub-specific configuration options",
    )

    appveyor: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="AppVeyor CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    azure: Optional[AzureConfig] = Field(
        default_factory=lambda: AzureConfig(),
        description="Azure Pipelines CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    bot: Optional[BotConfig] = Field(
        default_factory=lambda: BotConfig(),
        description="This dictates the behavior of the conda-forge auto-tick bot which issues automatic version updates/migrations for feedstocks.",
    )

    build_platform: Optional[Dict[Platforms, Platforms]] = Field(
        default_factory=dict,
        description="This is a mapping from the target platform to the build platform for the package to be built.",
    )

    build_with_mambabuild: Optional[bool] = Field(
        default=True,
        description="configures the conda-forge CI to run a debug build using the mamba solver. More information can be in the [mamba docs](https://conda-forge.org/docs/maintainer/maintainer_faq.html#mfaq-mamba-local).",
    )

    channel_priority: Optional[ChannelPriorityConfig] = Field(
        default="strict",
        description="The channel priority level for the conda solver during feedstock builds. This can be one of `strict`, `flexible`, or `disabled`. For more information, see the [Strict channel priority](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-channels.html#strict-channel-priority) section on conda documentation.",
    )

    channels: Optional[CondaForgeChannels] = Field(
        default_factory=lambda: CondaForgeChannels(),
        description="This represents the channels to grab packages from during builds and which channels/labels to push to on anaconda.org after a package has been built. The channels variable is a mapping with sources and targets.",
    )

    choco: Optional[List[str]] = Field(
        default_factory=list,
        description="This parameter allows for conda-smithy to run chocoloatey installs on Windows when additional system packages are needed. This is a list of strings that represent package names and any additional parameters.",
    )

    circle: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Circle CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    docker: Optional[CondaForgeDocker] = Field(
        default_factory=lambda: CondaForgeDocker(),
        description="This is a mapping for Docker-specific configuration options.",
    )

    idle_timeout_minutes: Optional[int] = Field(
        default=None,
        description="Configurable idle timeout.  Used for packages that don't have chatty enough builds. Applicable only to circleci and travis",
    )

    win_64: Optional[PlatformUniqueConfig] = Field(
        default_factory=lambda: PlatformUniqueConfig(),
        description="Windows-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
        validation_alias=AliasChoices("win_64", "win"),
    )

    osx_64: Optional[PlatformUniqueConfig] = Field(
        default_factory=lambda: PlatformUniqueConfig(),
        description="OSX-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
        validation_alias=AliasChoices("osx_64", "osx"),
    )

    osx_arm64: Optional[PlatformUniqueConfig] = Field(
        default_factory=lambda: PlatformUniqueConfig(),
        description="OSX-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    linux_64: Optional[PlatformUniqueConfig] = Field(
        default_factory=lambda: PlatformUniqueConfig(),
        description="Linux-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
        validation_alias=AliasChoices("linux_64", "linux"),
    )

    linux_aarch64: Optional[PlatformUniqueConfig] = Field(
        default_factory=lambda: PlatformUniqueConfig(),
        description="ARM-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    linux_ppc64le: Optional[PlatformUniqueConfig] = Field(
        default_factory=lambda: PlatformUniqueConfig(),
        description="PPC-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    linux_s390x: Optional[PlatformUniqueConfig] = Field(
        default_factory=lambda: PlatformUniqueConfig(),
        description="s390x-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    linux_armv7l: Optional[PlatformUniqueConfig] = Field(
        default_factory=lambda: PlatformUniqueConfig(),
        description="ARM-specific configuration options. This is largely an internal setting and should not normally be manually modified.",
    )

    @field_validator(
        "win_64",
        "osx_64",
        "linux_64",
        "linux_aarch64",
        "linux_ppc64le",
        "linux_s390x",
        "linux_armv7l",
    )
    @classmethod
    def validate_platform(
        cls,
        field_value,
        _info: FieldValidationInfo,
    ):
        print(f"{cls}: Field value {field_value}")
        if (
            field_value.enabled is False
            and _info.field_name in _info.data["build_platform"]
        ):
            raise ValueError(
                f"Platform {field_value} is disabled but is also a build platform."
                " Please enable the platform or remove it from build_platform."
            )
        return field_value

    noarch_platforms: Optional[List[Platforms]] = Field(
        default_factory=lambda: ["linux_64"],
        description="Platforms on which to build noarch packages. The preferred default is a single build on linux_64.",
    )

    os_version: Optional[Dict[Platforms, Optional[str]]] = Field(
        default_factory=dict,
        description="This key is used to set the OS versions for linux_* platforms. Valid entries map a linux platform and arch to either cos6 or cos7. Currently cos6 is the default for linux-64. All other linux architectures use CentOS 7.",
    )

    provider: Optional[
        Dict[Platforms, Union[List[CIservices], CIservices, bool, None]]
    ] = Field(
        default_factory=dict,
        description="The provider field is a mapping from build platform (not target platform) to CI service. It determines which service handles each build platform. If a desired build platform is not available with a selected provider (either natively or with emulation), the build will be disabled. Use the build_platform field to manually specify cross-compilation when no providers offer a desired build platform.",
    )

    package: Optional[str] = Field(
        default=None,
        description="Default location for a package feedstock directory basename.",
    )

    recipe_dir: Optional[str] = Field(
        default="recipe",
        description="The relative path to the recipe directory",
    )

    remote_ci_setup: Optional[List[str]] = Field(
        default_factory=lambda: ["conda-forge-ci-setup=3"],
        description="This option can be used to override the default conda-forge-ci-setup package. Can be given with ${url or channel_alias}::package_name, defaults to conda-forge channel_alias if no prefix is given.",
    )

    @field_validator("remote_ci_setup", mode="before")
    def validate_remote_ci_setup(cls, remote_ci_setup):
        _sanitized_remote_ci_setup = []
        for package in remote_ci_setup:
            _sanitized_remote_ci_setup.append(
                sanitize_remote_ci_setup(package)
            )
        return _sanitized_remote_ci_setup

    shellcheck: Optional[ShellCheck] = Field(
        default=None,
        description="Shell scripts used for builds or activation scripts can be linted with shellcheck. This option can be used to enable shellcheck and configure its behavior.",
    )

    skip_render: Optional[List[BotConfigSkipRenderChoices]] = Field(
        default_factory=list,
        description="This option specifies a list of files which conda smithy will skip rendering.",
    )

    templates: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="This is mostly an internal field for specifying where templates files live. You shouldn't need it.",
    )

    test_on_native_only: Optional[bool] = Field(
        default=False,
        description="This is used for disabling testing for cross compiling. Default is false. This has been deprecated in favor of the test top-level field. It is now mapped to test: native_and_emulated.",
    )

    test: Optional[
        Literal["all", "native_only", "native_and_emulated", "emulated_only"]
    ] = Field(
        default=None,
        description="This is used to configure on which platforms a recipe is tested. Default is all. ",
    )

    travis: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Travis CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    upload_on_branch: Optional[str] = Field(
        default=None,
        description="This parameter restricts uploading access on work from certain branches of the same repo. Only the branch listed in upload_on_branch will trigger uploading of packages to the target channel. The default is to skip this check if the key upload_on_branch is not in conda-forge.yml",
    )

    drone: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Drone CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    woodpecker: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Woodpecker CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
    )

    config_version: Optional[str] = Field(
        default="2",
        description="The version of the conda-forge.yml specification. This should not be manually modified.",
    )

    exclusive_config_file: Optional[str] = Field(
        default=None,
        description="Exclusive conda-build config file to replace conda-forge-pinning. For advanced usage only",
    )

    compiler_stack: Optional[str] = Field(
        default="comp7",
        description="Compiler stack environment variable",
    )

    min_py_ver: Optional[str] = Field(
        default="27",
        description="Minimum Python version",
    )

    max_py_ver: Optional[str] = Field(
        default="37",
        description="Maximum Python version",
    )

    min_r_ver: Optional[str] = Field(
        default="34",
        description="Minimum R version",
    )

    max_r_ver: Optional[str] = Field(
        default="34",
        description="Maximum R version",
    )

    github_actions: Optional[Dict[str, Any]] = Field(
        description="GitHub Actions CI settings. This is usually read-only and should not normally be manually modified. Tools like conda-smithy may modify this, as needed.",
        default_factory=dict,
    )

    private_upload: Optional[bool] = Field(
        default=False,
        description="Whether to upload to a private channel",
    )

    secrets: Optional[List[str]] = Field(
        default_factory=list,
        description="List of secrets to be used in GitHub Actions",
    )

    clone_depth: Optional[int] = Field(
        default=None,
        description="The depth of the git clone",
    )

    remote_ci_setup: Optional[List[str]] = Field(
        default_factory=lambda: ["conda-forge-ci-setup=3"],
        description="This option can be used to override the default conda-forge-ci-setup package. Can be given with ${url or channel_alias}::package_name, defaults to conda-forge channel_alias if no prefix is given.",
    )

    timeout_minutes: Optional[int] = Field(
        default=None,
        description="The timeout in minutes for all platforms CI jobs",
    )

    # Deprecated values, if passed should raise errors, only present for validation
    # Will not show up in the model dump, due to exclude=True

    matrix: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        exclude=True,
        description="Build matrices were used to specify a set of build configurations to run for each package pinned dependency. This has been deprecated in favor of the provider field. More information can be found in the [conda-forge docs](https://conda-forge.org/docs/maintainer/knowledge_base.html#build-matrices).",
    )

    @field_validator("matrix", mode="before")
    def matrix_deprecated(cls, v):
        if v is not None:
            raise ValueError(
                "Cannot rerender with matrix in conda-forge.yml."
                " Please migrate matrix to conda_build_config.yaml and try again."
                " See https://github.com/conda-forge/conda-smithy/wiki/Release-Notes-3.0.0.rc1"
                " for more info."
            )
        return v
