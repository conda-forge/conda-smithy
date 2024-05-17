# This model is also used for generating and automatic documentation for the conda-forge.yml file.
# For an upstream preview of the documentation, see https://conda-forge.org/docs/maintainer/conda_forge_yml.

import json
from enum import Enum
from inspect import cleandoc
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, create_model, ConfigDict

from conda.base.constants import KNOWN_SUBDIRS

try:
    from enum import StrEnum
except ImportError:
    from backports.strenum import StrEnum


from conda_smithy.validate_schema import (
    CONDA_FORGE_YAML_DEFAULTS_FILE,
    CONDA_FORGE_YAML_SCHEMA_FILE,
)

"""
Note: By default, we generate hints about additional fields the user added to the model
if extra="allow" is set. This can be disabled by inheriting from the NoExtraFieldsHint class
next to BaseModel.

If adding new fields, you should decide between extra="forbid" and extra="allow", since
extra="ignore" (the default) will not generate hints about additional fields.
"""


class Nullable(Enum):
    """Created to avoid issue with schema validation of null values in lists or dicts."""

    null = None


class NoExtraFieldsHint:
    """
    Inherit from this class next to BaseModel to disable hinting about extra fields, even
    if the model has `ConfigDict(extra="allow")`.
    """

    HINT_EXTRA_FIELDS = False


#############################################
######## Choices (Enum/Literals) definitions #########
#############################################

conda_build_tools = Literal[
    # will run vanilla conda-build, with system configured / default solver
    "conda-build",
    # will run vanilla conda-build, with the classic solver
    "conda-build+classic",
    # will run vanilla conda-build, with libmamba solver
    "conda-build+conda-libmamba-solver",
    # will run 'conda mambabuild', as provided by boa
    "mambabuild",
]


class CIservices(StrEnum):
    azure = "azure"
    circle = "circle"
    travis = "travis"
    appveyor = "appveyor"
    github_actions = "github_actions"
    drone = "drone"
    woodpecker = "woodpecker"
    default = "default"
    emulated = "emulated"
    native = "native"
    disable = "None"


class BotConfigAutoMergeChoice(StrEnum):
    VERSION = "version"
    MIGRATION = "migration"


class BotConfigInspectionChoice(StrEnum):
    HINT = "hint"
    HINT_ALL = "hint-all"
    HINT_SOURCE = "hint-source"
    HINT_GRAYSKULL = "hint-grayskull"
    UPDATE_ALL = "update-all"
    UPDATE_SOURCE = "update-source"
    UPDATE_GRAYSKULL = "update-grayskull"
    DISABLED = "disabled"


class BotConfigVersionUpdatesSourcesChoice(StrEnum):
    CRAN = "cran"
    GITHUB = "github"
    INCREMENT_ALPHA_RAW_URL = "incrementalpharawurl"
    LIBRARIES_IO = "librariesio"
    NPM = "npm"
    NVIDIA = "nvidia"
    PYPI = "pypi"
    RAW_URL = "rawurl"
    ROS_DISTRO = "rosdistro"


##############################################
########## Model definitions #################
##############################################


class AzureRunnerSettings(BaseModel, NoExtraFieldsHint):
    """This is the settings for runners."""

    model_config: ConfigDict = ConfigDict(extra="allow")

    pool: Optional[Dict[str, str]] = Field(
        default_factory=lambda: {"vmImage": "ubuntu-latest"},
        description="The pool of self-hosted runners, e.g. 'vmImage': 'ubuntu-latest'",
    )

    swapfile_size: Optional[Union[str, Nullable]] = Field(
        default=None, description="Swapfile size in GiB"
    )

    timeoutInMinutes: Optional[int] = Field(
        default=360, description="Timeout in minutes for the job"
    )

    variables: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Variables"
    )


class AzureFreeDiskSpaceConfig(StrEnum):
    CACHE = "cache"
    APT = "apt"
    DOCKER = "docker"


class AzureConfig(BaseModel):
    """
    This dictates the behavior of the Azure Pipelines CI service. It is a sub-mapping for
    Azure-specific configuration options. For more information and some variables
    specifications, see the [Azure Pipelines schema reference documentation](
    https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/?view=azure-pipelines).
    """

    model_config: ConfigDict = ConfigDict(extra="forbid")

    force: Optional[bool] = Field(
        default=False,
        description="Force building all supported providers",
    )

    free_disk_space: Optional[
        Union[bool, Nullable, List[Literal["apt", "cache", "docker"]]]
    ] = Field(
        default=False,
        description=cleandoc(
            """
            Free up disk space before running the Docker container for building on Linux.
            The following components can be cleaned up: `apt`, `cache`, `docker`.
            When set to `true`, only `apt` and `cache` are cleaned up.
            Set it to the full list to clean up all components.
            """
        ),
    )

    max_parallel: Optional[int] = Field(
        default=50,
        description="Limit the amount of CI jobs running concurrently at a given time",
    )

    project_id: Optional[str] = Field(
        default="84710dde-1620-425b-80d0-4cf5baca359d",
        description="The ID of the Azure Pipelines project",
    )

    project_name: Optional[str] = Field(
        default="feedstock-builds",
        description="The name of the Azure Pipelines project",
    )

    build_id: Optional[int] = Field(
        default=None,
        description=cleandoc(
            """
            The build ID for the specific feedstock used for rendering the badges in the
            README file generated. When the value is None, conda-smithy will compute the
            build ID by calling the Azure API which requires a token for private azure
            projects.
            """
        ),
    )

    upload_packages: Optional[bool] = Field(
        default=True,
        description="Whether to upload the packages to Anaconda.org. Useful for testing.",
    )

    #########################################
    ##### Self-hosted runners settings ######
    #########################################
    settings_linux: AzureRunnerSettings = Field(
        default_factory=lambda: AzureRunnerSettings(swapfile_size="0GiB"),
        description="Linux-specific settings for runners",
    )

    settings_osx: AzureRunnerSettings = Field(
        default_factory=lambda: AzureRunnerSettings(
            pool={"vmImage": "macOS-12"}
        ),
        description="OSX-specific settings for runners",
    )

    settings_win: AzureRunnerSettings = Field(
        default_factory=lambda: AzureRunnerSettings(
            pool={"vmImage": "windows-2022"},
            variables={
                "CONDA_BLD_PATH": "D:\\\\bld\\\\",
                "UPLOAD_TEMP": "D:\\\\tmp",
            },
        ),
        description="Windows-specific settings for runners",
    )

    user_or_org: Optional[Union[str, Nullable]] = Field(
        default=None,
        description="The name of the Azure user or organization. Defaults to the "
        "value of github: user_or_org.",
        exclude=True,  # Will not be rendered in the model dump since we check if it was
        # set or not
    )

    store_build_artifacts: Optional[bool] = Field(
        default=False,
        description="Store the conda build_artifacts directory as an \
        Azure pipeline artifact",
    )

    timeout_minutes: Optional[Union[int, Nullable]] = Field(
        default=None,
        description="The maximum amount of time (in minutes) that a \
            job can run before it is automatically canceled",
    )


class GithubConfig(BaseModel):
    model_config: ConfigDict = ConfigDict(extra="forbid")

    user_or_org: Optional[str] = Field(
        description="The name of the GitHub user or organization",
        default="conda-forge",
    )
    repo_name: Optional[str] = Field(
        description="The name of the repository",
        default="",
    )
    branch_name: Optional[str] = Field(
        description="The name of the branch to execute on",
        default="main",
    )
    tooling_branch_name: Optional[str] = Field(
        description="The name of the branch to use for rerender+webservices \
            github actions and conda-forge-ci-setup-feedstock references",
        default="main",
    )


class GithubActionsConfig(BaseModel):
    model_config: ConfigDict = ConfigDict(extra="forbid")

    artifact_retention_days: Optional[int] = Field(
        description="The number of days to retain artifacts",
        default=14,
    )

    cancel_in_progress: Optional[bool] = Field(
        description="Whether to cancel jobs in the same build if one fails.",
        default=True,
    )

    free_disk_space: Optional[
        Union[bool, Nullable, List[Literal["apt", "cache", "docker"]]]
    ] = Field(
        default=False,
        description=cleandoc(
            """
            Free up disk space before running the Docker container for building on Linux.
            The following components can be cleaned up: `apt`, `cache`, `docker`.
            When set to `true`, only `apt` and `cache` are cleaned up.
            Set it to the full list to clean up all components.
            """
        ),
    )

    max_parallel: Optional[Union[int, Nullable]] = Field(
        description="The maximum number of jobs to run in parallel",
        default=None,
    )

    self_hosted: Optional[bool] = Field(
        description="Whether to use self-hosted runners",
        default=False,
    )

    store_build_artifacts: Optional[bool] = Field(
        description="Whether to store build artifacts",
        default=False,
    )

    timeout_minutes: Optional[int] = Field(
        default=360,
        description="The maximum amount of time (in minutes) that a \
            job can run before it is automatically canceled",
    )

    triggers: Optional[list] = Field(
        default=[],
        description="Triggers for Github Actions. Defaults to push, pull_request, \
            when not self-hosted and push when self-hosted",
    )

    upload_packages: Optional[bool] = Field(
        default=True,
        description="Whether to upload the packages to Anaconda.org. Useful for testing.",
    )


class BotConfigVersionUpdates(BaseModel):
    """
    This dictates the behavior of the conda-forge auto-tick bot for version
    updates
    """

    model_config: ConfigDict = ConfigDict(extra="forbid")

    random_fraction_to_keep: Optional[float] = Field(
        None,
        description="Fraction of versions to keep for frequently updated packages",
    )

    exclude: Optional[List[str]] = Field(
        default=[],
        description="List of versions to exclude. "
        "Make sure branch names are `str` by quoting the value.",
    )

    sources: Optional[List[BotConfigVersionUpdatesSourcesChoice]] = Field(
        None,
        description="List of sources to use for version updates",
    )


class BotConfig(BaseModel):
    """
    This dictates the behavior of the conda-forge auto-tick bot which issues
    automatic version updates/migrations for feedstocks.
    """

    model_config: ConfigDict = ConfigDict(extra="forbid")

    automerge: Optional[Union[bool, BotConfigAutoMergeChoice]] = Field(
        False,
        description="Automatically merge PRs if possible",
    )

    check_solvable: Optional[bool] = Field(
        default=True,
        description="Open PRs only if resulting environment is solvable.",
    )

    inspection: Optional[BotConfigInspectionChoice] = Field(
        default="hint",
        description="Method for generating hints or updating recipe",
    )

    abi_migration_branches: Optional[List[str]] = Field(
        default=[],
        description="List of branches for additional bot migration PRs. "
        "Make sure branch names are `str` by quoting the value.",
    )

    run_deps_from_wheel: Optional[bool] = Field(
        default=False,
        description="Update run dependencies from the pip wheel",
    )

    version_updates: Optional[BotConfigVersionUpdates] = Field(
        default_factory=BotConfigVersionUpdates,
        description="Bot config for version update PRs",
    )


class CondaBuildConfig(BaseModel, NoExtraFieldsHint):
    model_config: ConfigDict = ConfigDict(extra="allow")

    pkg_format: Optional[Literal["tar", 1, 2, "1", "2"]] = Field(
        description="The package version format for conda build.",
        default=2,
    )

    zstd_compression_level: Optional[int] = Field(
        default=16,
        description=cleandoc(
            """The compression level for the zstd compression algorithm for
            .conda artifacts. conda-forge uses a default value of 16 for a good
            compromise of performance and compression."""
        ),
    )

    error_overlinking: Optional[bool] = Field(
        default=False,
        description=cleandoc(
            """
            Enable error when shared libraries from transitive dependencies are
            directly  linked  to any executables or shared libraries in  built
            packages. For more details, see the
            [conda build documentation](https://docs.conda.io/projects/conda-build/en/stable/resources/commands/conda-build.html).
            """
        ),
    )


class CondaForgeDocker(BaseModel):
    model_config: ConfigDict = ConfigDict(extra="forbid")

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

    #########################################
    #### Deprecated Docker configuration ####
    #########################################
    interactive: Optional[Union[bool, Nullable]] = Field(
        description="Whether to run Docker in interactive mode",
        default=None,
        deprecated=True,
    )


class ShellCheck(BaseModel):
    model_config: ConfigDict = ConfigDict(extra="forbid")

    enabled: bool = Field(
        description="Whether to use shellcheck to lint shell scripts",
        default=False,
    )


class PlatformsAliases(StrEnum):
    linux = "linux"
    win = "win"
    osx = "osx"


def get_subdirs():
    return [
        subdir.replace("-", "_") for subdir in KNOWN_SUBDIRS if "-" in subdir
    ]


Platforms = StrEnum("Platforms", get_subdirs())


class ChannelPriorityConfig(StrEnum):
    STRICT = "strict"
    FLEXIBLE = "flexible"
    DISABLED = "disabled"


class DefaultTestPlatforms(StrEnum):
    all = "all"
    native = "native"
    native_and_emulated = "native_and_emulated"


BuildPlatform = create_model(
    "build_platform",
    **{
        platform.value: (Optional[Platforms], Field(default=platform.value))
        for platform in Platforms
    },
    __config__=ConfigDict(extra="allow"),
)

OSVersion = create_model(
    "os_version",
    **{
        platform.value: (Optional[Union[str, Nullable]], Field(default=None))
        for platform in Platforms
        if platform.value.startswith("linux")
    },
    __config__=ConfigDict(extra="allow"),
)

ProviderType = Union[List[CIservices], CIservices, bool, Nullable]

Provider = create_model(
    "provider",
    **dict(
        [
            (str(plat), (Optional[ProviderType], Field(default=None)))
            for plat in list(PlatformsAliases) + list(Platforms)
        ]
        + [
            (str(plat), (Optional[ProviderType], Field(default="azure")))
            for plat in ("linux_64", "osx_64", "win_64")
        ]
    ),
    __config__=ConfigDict(extra="allow"),
)


class ConfigModel(BaseModel):
    """
    This model describes in detail the top-level fields in  `conda-forge.yml`.
    General configuration options are described below within the `Fields`
    specifications. Additional examples are provided as part of the object
    description. Values and options are subject to change, and will be
    flagged as Deprecated as appropriate.
    """

    model_config: ConfigDict = ConfigDict(extra="forbid")

    # Values which are not expected to be present in the model dump, are
    # flagged with exclude=True. This is to avoid confusion when comparing
    # the model dump with the default conda-forge.yml file used for smithy
    # or to avoid deprecated values being rendered.

    conda_build: Optional[CondaBuildConfig] = Field(
        default_factory=CondaBuildConfig,
        description=cleandoc(
            """
        Settings in this block are used to control how `conda build`
        runs and produces artifacts. An example of the such configuration is:

        ```yaml
        conda_build:
            pkg_format: 2
            zstd_compression_level: 16
            error_overlinking: False
        ```
        """
        ),
    )

    conda_build_tool: Optional[conda_build_tools] = Field(
        default="conda-build",
        description=cleandoc(
            """
        Use this option to choose which tool is used to build your recipe.
        """
        ),
    )

    conda_install_tool: Optional[Literal["conda", "mamba"]] = Field(
        default="mamba",
        description=cleandoc(
            """
        Use this option to choose which tool is used to provision the tooling in your
        feedstock.
        """
        ),
    )

    conda_forge_output_validation: Optional[bool] = Field(
        default=False,
        description=cleandoc(
            """
        This field must be set to `True` for feedstocks in the `conda-forge` GitHub
        organization. It enables the required feedstock artifact validation as described
        in [Output Validation and Feedstock Tokens](/docs/maintainer/infrastructure#output-validation).
        """
        ),
    )

    conda_solver: Optional[Union[Literal["libmamba", "classic"], Nullable]] = (
        Field(
            default="libmamba",
            description=cleandoc(
                """
        Choose which `conda` solver plugin to use for feedstock builds.
        """
            ),
        )
    )

    github: Optional[GithubConfig] = Field(
        default_factory=GithubConfig,
        description=cleandoc(
            """
        Mapping for GitHub-specific configuration options. The defaults are as follows:

        ```yaml
        github:
            user_or_org: conda-forge
            repo_name: "my_repo"
            branch_name: main
            tooling_branch_name: main
        ```
        """
        ),
    )

    bot: Optional[BotConfig] = Field(
        default_factory=BotConfig,
        description=cleandoc(
            """
        This dictates the behavior of the conda-forge auto-tick bot which issues
        automatic version updates/migrations for feedstocks.
        A valid example is:

        ```yaml
        bot:
            # can the bot automerge PRs it makes on this feedstock
            automerge: true
            # only automerge on successful version PRs, migrations are not automerged
            automerge: 'version'
            # only automerge on successful migration PRs, versions are not automerged
            automerge: 'migration'

            # only open PRs if resulting environment is solvable, useful for tightly coupled packages
            check_solvable: true

            # The bot.inspection key in the conda-forge.yml can have one of seven possible values and controls
            # the bots behaviour for automatic dependency updates:
            inspection: hint  # generate hints using source code (backwards compatible)
            inspection: hint-all  # generate hints using all methods
            inspection: hint-source  # generate hints using only source code
            inspection: hint-grayskull  # generate hints using only grayskull
            inspection: update-all  # update recipe using all methods
            inspection: update-source  # update recipe using only source code
            inspection: update-grayskull  # update recipe using only grayskull
            inspection: disabled # don't update recipe, don't generate hints

            # any branches listed in this section will get bot migration PRs in addition
            # to the default branch
            abi_migration_branches:
                - 'v1.10.x'

            version_updates:
                # use this for packages that are updated too frequently
                random_fraction_to_keep: 0.1  # keeps 10% of versions at random
                exclude:
                    - '08.14'
        ```

        The `abi_migration_branches` feature is useful to, for example, add a
        long-term support (LTS) branch for a package.
        """
        ),
    )

    build_platform: Optional[BuildPlatform] = Field(
        default_factory=BuildPlatform,
        description=cleandoc(
            """
        This is a mapping from the target platform to the build platform for the
        package to be built. For example, the following builds a `osx-64` package
        on the `linux-64` build platform using cross-compiling.

        ```yaml
        build_platform:
            osx_64: linux_64
        ```

        Leaving this field empty implicitly requests to build a package natively. i.e.

        ```yaml
        build_platform:
            linux_64: linux_64
            linux_ppc64le: linux_ppc64le
            linux_aarch64: linux_aarch64
            osx_64: osx_64
            osx_arm64: osx_arm64
            win_64: win_64
        ```
        """
        ),
    )

    channel_priority: Optional[ChannelPriorityConfig] = Field(
        default="strict",
        description=cleandoc(
            """
        The channel priority level for the conda solver during feedstock builds.
        For extra information, see the
        [Strict channel priority](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-channels.html#strict-channel-priority)
        section on conda documentation.
        """
        ),
    )

    choco: Optional[List[str]] = Field(
        default_factory=list,
        description=cleandoc(
            """
        This parameter allows for conda-smithy to run chocoloatey installs on Windows
        when additional system packages are needed. This is a list of strings that
        represent package names and any additional parameters. For example,

        ```yaml
        choco:
            # install a package
            - nvidia-display-driver

            # install a package with a specific version
            - cuda --version=11.0.3
        ```

        This is currently only implemented for Azure Pipelines. The command that is run is
        `choco install {entry} -fdv -y --debug`.  That is, `choco install` is executed
        with a standard set of additional flags that are useful on CI.
        """
        ),
    )

    docker: Optional[CondaForgeDocker] = Field(
        default_factory=CondaForgeDocker,
        description=cleandoc(
            """
        This is a mapping for Docker-specific configuration options.
        Some options are

        ```yaml
        docker:
            executable: docker
            command: "bash"
        ```
        """
        ),
    )

    idle_timeout_minutes: Optional[Union[int, Nullable]] = Field(
        default=None,
        description=cleandoc(
            """
        Configurable idle timeout. Used for packages that don't have chatty enough
        builds. Applicable only to circleci and travis.

        ```yaml
        idle_timeout_minutes: 60
        ```
        """
        ),
    )

    noarch_platforms: Optional[Union[Platforms, List[Platforms]]] = Field(
        default_factory=lambda: ["linux_64"],
        description=cleandoc(
            """
        Platforms on which to build noarch packages. The preferred default is a
        single build on `linux_64`.

        ```yaml
        noarch_platforms: linux_64
        ```

        To build on multiple platforms, e.g. for simple packages with platform-specific
        dependencies, provide a list.

        ```yaml
        noarch_platforms:
          - linux_64
          - win_64
        ```
        """
        ),
    )

    os_version: Optional[OSVersion] = Field(
        default_factory=OSVersion,
        description=cleandoc(
            """
        This key is used to set the OS versions for `linux_*` platforms. Valid entries
        map a linux platform and arch to either `cos6` or `cos7`.
        Currently `cos6` is the default for `linux-64`.
        All other linux architectures use CentOS 7.
        Here is an example that enables CentOS 7 on `linux-64` builds

        ```yaml
        os_version:
            linux_64: cos7
        ```
        """
        ),
    )

    provider: Optional[Provider] = Field(
        default_factory=Provider,
        description=cleandoc(
            """
        The `provider` field is a mapping from build platform (not target platform)
        to CI service. It determines which service handles each build platform.
        If a desired build platform is not available with a selected provider
        (either natively or with emulation), the build will be disabled.
        Use the `build_platform` field to manually specify cross-compilation when
        no providers offer a desired build platform.

        The following are available as supported build platforms:

        * `linux_64`
        * `osx_64`
        * `win_64`
        * `linux_aarch64`
        * `linux_ppc64le`
        * `linux_s390x`
        * `linux_armv7l`

        The following CI services are available:

        * `azure`
        * `circle`
        * `travis`
        * `appveyor`
        * `None` or `False` to disable a build platform.
        * `default` to choose an appropriate CI (only if available)
        * `native` to choose an appropriate CI for native compiling (only if available)
        * `emulated` to choose an appropriate CI for compiling inside an emulation
          of the target platform (only if available)

        For example, switching linux_64 & osx_64 to build on Travis CI, with win_64 on
        Appveyor:

        ```yaml
        provider:
            linux_64: travis
            osx_64: travis
            win_64: appveyor
        ```

        Currently, x86_64 platforms are enabled, but other build platforms are
        disabled by default. i.e. an empty provider entry is equivalent to the
        following:

        ```yaml
        provider:
            linux_64: azure
            osx_64: azure
            win_64: azure
            linux_ppc64le: None
            linux_aarch64: None
        ```

        To enable `linux_ppc64le` and `linux_aarch64` add the following:

        ```yaml
        provider:
            linux_ppc64le: default
            linux_aarch64: default
        ```
        """
        ),
    )

    package: Optional[Union[str, Nullable]] = Field(
        default=None,
        exclude=True,  # Will not be rendered in the model dump
        description="Default location for a package feedstock directory basename.",
    )

    recipe_dir: Optional[str] = Field(
        default="recipe",
        description=cleandoc(
            """
        The relative path to the recipe directory. The default is:

        ```yaml
        recipe_dir: recipe
        ```
        """
        ),
    )

    remote_ci_setup: Optional[Union[str, List[str]]] = Field(
        default_factory=lambda: [
            "conda-forge-ci-setup=4",
            "conda-build>=24.1",
        ],
        description=cleandoc(
            """
        This option can be used to override the default `conda-forge-ci-setup` package.
        Can be given with `${url or channel_alias}::package_name`,
        defaults to conda-forge channel_alias if no prefix is given.

        ```yaml
        remote_ci_setup: ["conda-forge-ci-setup=4", "conda-build>=24.1"]
        ```
        """
        ),
    )

    shellcheck: Optional[Union[ShellCheck, Nullable]] = Field(
        default_factory=lambda: {"enabled": False},
        description=cleandoc(
            """
        Shell scripts used for builds or activation scripts can be linted with
        shellcheck. This option can be used to enable shellcheck and configure
        its behavior. This is not enabled by default, but can be enabled like so:

        ```yaml
        shellcheck:
            enabled: True
        ```
        """
        ),
    )

    skip_render: Optional[List[str]] = Field(
        default_factory=list,
        description=cleandoc(
            """
        This option specifies a list of files which `conda smithy` will skip rendering.
        This is useful for files that are not templates, but are still in the recipe
        directory. The default value is an empty list `[]`, which will consider that
        all files can be rendered. For example, if you want to skip rendering
        the `.gitignore` and `LICENSE.txt` files, you can add the following:

        ```yaml
        skip_render:
            - .gitignore
            - LICENSE.txt
        ```
        """
        ),
    )

    templates: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description=cleandoc(
            """
        This is mostly an internal field for specifying where template files reside.
        You shouldn't need to modify it.
        """
        ),
    )

    test_on_native_only: Optional[bool] = Field(
        default=False,
        deprecated=True,
        description=cleandoc(
            """
        This was used for disabling testing for cross-compiling.

        ```warning
        This has been deprecated in favor of the top-level `test` field.
        It is now mapped to `test: native_and_emulated`.
        ```
        """
        ),
    )

    test: Optional[Union[DefaultTestPlatforms, Nullable]] = Field(
        default=None,
        description=cleandoc(
            """
        This is used to configure on which platforms a recipe is tested.

        ```yaml
        test: native_and_emulated
        ```

        Will do testing only if the platform is native or if there is an emulator.

        ```yaml
        test: native
        ```

        Will do testing only if the platform is native.
        """
        ),
    )

    upload_on_branch: Optional[Union[str, Nullable]] = Field(
        default=None,
        exclude=True,  # Will not be rendered in the model dump
        description=cleandoc(
            """
        This parameter restricts uploading access on work from certain branches of the
        same repo. Only the branch listed in `upload_on_branch` will trigger uploading
        of packages to the target channel. The default is to skip this check if the key
        `upload_on_branch` is not in `conda-forge.yml`. To restrict uploads to the
        main branch:

        ```yaml
        upload_on_branch: main
        ```
        """
        ),
    )

    config_version: Optional[str] = Field(
        default="2",
        description=cleandoc(
            """
        The conda-smithy config version to be used for conda_build_config.yaml
        files in recipe and conda-forge-pinning. This should not be manually modified.
        """
        ),
    )

    exclusive_config_file: Optional[Union[str, Nullable]] = Field(
        default=None,
        exclude=True,  # Will not be rendered in the model dump
        description=cleandoc(
            """
        Exclusive conda-build config file to replace `conda-forge-pinning`.
        For advanced usage only.
        """
        ),
    )

    compiler_stack: Optional[str] = Field(
        default="comp7",
        deprecated=True,
        description=cleandoc(
            """
        Compiler stack environment variable. This is used to specify the compiler
        stack to use for builds. Deprecated.

        ```yaml
        compiler_stack: comp7
        ```
        """
        ),
    )

    min_py_ver: Optional[str] = Field(
        default="27",
        deprecated=True,
        description=cleandoc(
            """
        Minimum Python version. This is used to specify the minimum Python version
        to use for builds. Deprecated.

        ```yaml
        min_py_ver: 27
        ```
        """
        ),
    )

    max_py_ver: Optional[str] = Field(
        default="37",
        deprecated=True,
        description=cleandoc(
            """
        Maximum Python version. This is used to specify the maximum Python version
        to use for builds. Deprecated.

        ```yaml
        max_py_ver: 37
        ```
        """
        ),
    )

    min_r_ver: Optional[str] = Field(
        default="34",
        deprecated=True,
        description=cleandoc(
            """
        Minimum R version. This is used to specify the minimum R version to
        use for builds. Deprecated.

        ```yaml
        min_r_ver: 34
        ```
        """
        ),
    )

    max_r_ver: Optional[str] = Field(
        default="34",
        deprecated=True,
        description=cleandoc(
            """
        Maximum R version. This is used to specify the maximum R version to use
        for builds. Deprecated.

        ```yaml
        max_r_ver: 34
        ```
        """
        ),
    )

    private_upload: Optional[bool] = Field(
        default=False,
        description=cleandoc(
            """
        Whether to upload to a private channel.

        ```yaml
        private_upload: False
        ```
        """
        ),
    )

    secrets: Optional[List[str]] = Field(
        default_factory=list,
        description=cleandoc(
            """
        List of secrets to be used in GitHub Actions.
        The default is an empty list and will not be used.
        """
        ),
    )

    clone_depth: Optional[Union[int, Nullable]] = Field(
        default=None,
        description=cleandoc(
            """
        The depth of the git clone.
        """
        ),
    )

    ###################################
    ####       CI Providers        ####
    ###################################
    travis: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description=cleandoc(
            """
        Travis CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """
        ),
    )

    circle: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description=cleandoc(
            """
        Circle CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """
        ),
    )

    appveyor: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"image": "Visual Studio 2017"},
        description=cleandoc(
            """
        AppVeyor CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """
        ),
    )

    azure: Optional[AzureConfig] = Field(
        default_factory=AzureConfig,
        description=cleandoc(
            """
        Azure Pipelines CI settings. This is usually read-only and should not
        normally be manually modified. Tools like conda-smithy may modify this, as needed.
        For example:

        ```yaml
        azure:
            # flag for forcing the building all supported providers
            force: False
            # toggle for storing the conda build_artifacts directory (including the
            # built packages) as an Azure pipeline artifact that can be downloaded
            store_build_artifacts: False
            # toggle for freeing up some extra space on the default Azure Pipelines
            # linux image before running the Docker container for building
            free_disk_space: False
            # limit the amount of CI jobs running concurrently at a given time
            # each OS will get its proportional share of the configured value
            max_parallel: 25
        ```

        Below is an example configuration for setting up a self-hosted Azure agent for Linux:

        ```yaml
        azure:
            settings_linux:
            pool:
                name: your_local_pool_name
                demands:
                  - some_key -equals some_value
            workspace:
                clean: all
            strategy:
                maxParallel: 1
        ```

        Below is an example configuration for adding a swapfile on an Azure agent for Linux:

        ```yaml
        azure:
            settings_linux:
                swapfile_size: 10GiB
        ```
        """
        ),
    )

    drone: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description=cleandoc(
            """
        Drone CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """
        ),
    )

    github_actions: Optional[GithubActionsConfig] = Field(
        default_factory=GithubActionsConfig,
        description=cleandoc(
            """
        GitHub Actions CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """
        ),
    )

    woodpecker: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description=cleandoc(
            """
        Woodpecker CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """
        ),
    )

    ###################################
    ####       Deprecated          ####
    ###################################

    # Deprecated values, only present for validation will not show up in
    # the model dump, due to exclude=True

    build_with_mambabuild: Optional[bool] = Field(
        default=True,
        exclude=True,
        deprecated=True,
        description=cleandoc(
            """
        build_with_mambabuild is deprecated, use `conda_build_tool` instead.
        """
        ),
    )

    matrix: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        exclude=True,
        deprecated=True,
        description=cleandoc(
            """
        Build matrices were used to specify a set of build configurations to run for each
        package pinned dependency. This has been deprecated in favor of the `provider` field.
        More information can be found in the
        [Build Matrices](/docs/maintainer/knowledge_base/#build-matrices) section of the
        conda-forge docs.
        """
        ),
    )


if __name__ == "__main__":
    # This is used to generate the model dump for conda-smithy internal use
    # and for documentation purposes.

    model = ConfigModel()

    with CONDA_FORGE_YAML_SCHEMA_FILE.open(mode="w+") as f:
        obj = model.model_json_schema()
        f.write(json.dumps(obj, indent=2))
        f.write("\n")

    with CONDA_FORGE_YAML_DEFAULTS_FILE.open(mode="w+") as f:
        f.write(yaml.dump(model.model_dump(), indent=2))
