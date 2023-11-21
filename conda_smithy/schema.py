# This model is also used for generating and automatic documentation for the conda-forge.yml file. The documentation is generated using sphinx and "pydantic-autodoc" extension. For an upstream preview of the documentation, see https://conda-forge.org/docs/maintainer/conda_forge_yml.html.

import json
from enum import Enum, EnumMeta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Type, Union

import jsonschema
import yaml
from jsonschema import Draft7Validator, validators
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel, Field, create_model


def validate_json_schema(config, schema_file: str = None):
    # Validate the merged configuration against a JSON schema
    json_schema_file = (
        Path(__file__).resolve().parent / "data" / "conda-forge.v2.json"
    )

    if schema_file:
        json_schema_file = schema_file

    with open(json_schema_file, "r") as fh:
        _json_schema = json.loads(fh.read())

    validator = Draft7Validator(_json_schema)
    return list(validator.iter_errors(config))


class Nullable(Enum):
    """Created to avoid issue with schema validation of null values in lists or dicts."""

    null = None


class PydanticModelGenerator:
    """
    A utility class for generating Pydantic models based on an Enum for keys and a Pydantic model for values.

    This class is designed to help mitigate an issue when working with JSON Schema and Pydantic where Enumerators
    and Dicts do not work well with the generated model. It allows you to dynamically create Pydantic models for
    cases where you need to map enum values to corresponding data structures.

    Args:
        enum_class (Union[Type[Enum], Type[EnumMeta]]): A single Enum class or a Union of Enum classes representing the keys for the generated model.
        value_model (BaseModel): A Pydantic model representing the structure of the values.
        model_name (str): The name of the generated Pydantic model.

    Example usage:

    ```python
    class MyEnum1(str, Enum):
        key1 = "key1"
        key2 = "key2"

    class MyEnum2(str, Enum):
        key3 = "key3"
        key4 = "key4"

    class ValueModel(BaseModel):
        value_field: int

    # Create an instance of PydanticModelGenerator with a single Enum
    model_generator1 = PydanticModelGenerator(MyEnum1, ValueModel, "MyGeneratedModel1")

    # Create an instance of PydanticModelGenerator with a Union of Enums
    model_generator2 = PydanticModelGenerator(Union[MyEnum1, MyEnum2], ValueModel, "MyGeneratedModel2")

    # Retrieve the generated models using the __call__ method
    GeneratedModel1 = model_generator1()
    GeneratedModel2 = model_generator2()
    ```
    """

    def __init__(
        self,
        enum_class: Union[Type[Enum], Type[EnumMeta]],
        value_model: BaseModel,
        model_name: str,
    ):
        self.enum_class = enum_class
        self.value_model = value_model
        self.model_name = model_name

    def __call__(self) -> BaseModel:
        field_definitions = {}

        if hasattr(self.enum_class, "__args__"):
            # Handle Union types
            for enum_type in self.enum_class.__args__:
                if isinstance(enum_type, type) and issubclass(enum_type, Enum):
                    for enum_item in enum_type:
                        field_definitions[enum_item.value] = (
                            Optional[self.value_model],
                            {"description": f"The {enum_item.value} value"},
                        )
        else:
            # Handle single Enum
            for enum_item in self.enum_class:
                field_definitions[enum_item.value] = (
                    Optional[self.value_model],
                    {"description": f"The {enum_item.value} value"},
                )

        return create_model(self.model_name, **field_definitions)


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


class CIservices(str, Enum):
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


##############################################
########## Model definitions #################
##############################################


class AzureRunnerSettings(BaseModel):
    """This is the settings for self-hosted runners."""

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


class AzureConfig(BaseModel):
    """
    This dictates the behavior of the Azure Pipelines CI service. It is a sub-mapping for Azure-specific configuration options. For more information and some variables specifications, see the [Azure Pipelines schema reference documentation](https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/?view=azure-pipelines).
    """

    force: Optional[bool] = Field(
        default=False,
        description="Force building all supported providers",
    )

    free_disk_space: Optional[Union[bool, Nullable]] = Field(
        default=None,
        description="Free up disk space before running the Docker container for building on Linux",
        exclude=True,  # Will not be rendered in the model dump
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

    #########################################
    ##### Self-hosted runners settings ######
    #########################################
    settings_linux: AzureRunnerSettings = Field(
        default_factory=lambda: AzureRunnerSettings(swapfile_size="0GiB"),
        description="Linux-specific settings for self-hosted runners",
    )

    settings_osx: AzureRunnerSettings = Field(
        default_factory=lambda: AzureRunnerSettings(
            pool={"vmImage": "macOS-11"}
        ),
        description="OSX-specific settings for self-hosted runners",
    )

    settings_win: AzureRunnerSettings = Field(
        default_factory=lambda: AzureRunnerSettings(
            pool={"vmImage": "windows-2022"},
            variables={
                "CONDA_BLD_PATH": "D:\\\\bld\\\\",
                "UPLOAD_TEMP": "D:\\\\tmp",
            },
        ),
        description="Windows-specific settings for self-hosted runners",
    )

    user_or_org: Optional[Union[str, Nullable]] = Field(
        default=None,
        description="The name of the GitHub user or organization, if passed with \
        the GithubConfig provider, must comply with the value of the user_or_org field",
        exclude=True,  # Will not be rendered in the model dump
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
    user_or_org: Optional[str] = Field(
        description="The name of the GitHub user or organization, \
        if passed with the AzureConfig provider, must comply with the value of the user_or_org field",
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
    artifact_retention_days: Optional[int] = Field(
        description="The number of days to retain artifacts",
        default=14,
    )

    cancel_in_progress: Optional[bool] = Field(
        description="Whether to cancel jobs in the same build if one fails.",
        default=True,
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


class PlatformUniqueConfig(BaseModel):
    enabled: bool = Field(
        description="Whether to use extra platform-specific configuration options",
        default=False,
    )


class BotConfig(BaseModel):
    """
    This dictates the behavior of the conda-forge auto-tick bot which issues
    automatic version updates/migrations for feedstocks.
    """

    automerge: Optional[Union[bool, BotConfigAutoMergeChoice]] = Field(
        False,
        description="Automatically merge PRs if possible",
    )

    check_solvable: Optional[bool] = Field(
        None,
        description="Open PRs only if resulting environment is solvable.",
        exclude=True,  # Will not be rendered in the model dump
    )

    inspection: Optional[Union[bool, BotConfigInspectionChoice]] = Field(
        None,
        description="Method for generating hints or updating recipe",
        exclude=True,  # Will not be rendered in the model dump
    )

    abi_migration_branches: Optional[List[Union[str, int, float]]] = Field(
        None,
        description="List of branches for additional bot migration PRs",
        exclude=True,  # Will not be rendered in the model dump
    )

    version_updates_random_fraction_to_keep: Optional[float] = Field(
        None,
        description="Fraction of versions to keep for frequently updated packages",
        exclude=True,  # Will not be rendered in the model dump
    )


class CondaBuildConfig(BaseModel):
    pkg_format: Optional[Literal["tar", 1, 2, "1", "2"]] = Field(
        description="The package version format for conda build.",
        default=2,
    )

    zstd_compression_level: Optional[int] = Field(
        default=16,
        description="""The compression level for the zstd compression algorithm for
            .conda artifacts. conda-forge uses a default value of 16 for a good
            compromise of performance and compression.""",
    )

    error_overlinking: Optional[bool] = Field(
        default=False,
        description="""
            Enable error when shared libraries from transitive dependencies are
            directly  linked  to any executables or shared libraries in  built
            packages. For more details, see the
            [conda build documentation](https://docs.conda.io/projects/conda-build/en/stable/resources/commands/conda-build.html).
            """,
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

    interactive: Optional[Union[bool, Nullable]] = Field(
        description="Whether to run Docker in interactive mode",
        default=None,
        exclude=True,  # Will not be rendered in the model dump
    )

    #########################################
    #### Deprecated Docker configuration ####
    #########################################
    image: Optional[Union[str, Nullable]] = Field(
        description="""Setting the Docker image in conda-forge.yml is no longer
        supported, use conda_build_config.yaml to specify Docker images.""",
        default=None,
        exclude=True,  # Will not be rendered in the model dump
    )


class ShellCheck(BaseModel):
    enabled: bool = Field(
        description="Whether to use shellcheck to lint shell scripts",
        default=False,
    )


class PlatformsAliases(str, Enum):
    linux = "linux"
    win = "win"
    osx = "osx"


class Platforms(str, Enum):
    linux_64 = "linux_64"
    linux_aarch64 = "linux_aarch64"
    linux_armv7l = "linux_armv7l"
    linux_ppc64le = "linux_ppc64le"
    linux_s390x = "linux_s390x"
    win_64 = "win_64"
    osx_64 = "osx_64"
    osx_arm64 = "osx_arm64"


class ChannelPriorityConfig(str, Enum):
    STRICT = "strict"
    FLEXIBLE = "flexible"
    DISABLED = "disabled"


class DefaultTestPlatforms(str, Enum):
    all = "all"
    native_only = "native_only"
    native_and_emulated = "native_and_emulated"
    emulated_only = "emulated_only"


class ConfigModel(BaseModel):
    """
    This model describes in detail the top-level fields in  ``conda-forge.yml``.
    General configuration options are described below within the ``Fields``
    specifications. Additional examples are provided as part of the object
    description. Values and options are subject to change, and will be
    flagged as Deprecated as appropriate.

    """

    # Values which are not expected to be present in the model dump, are
    # flagged with exclude=True. This is to avoid confusion when comparing
    # the model dump with the default conda-forge.yml file used for smithy
    # or to avoid deprecated values been rendered.

    conda_build: Optional[CondaBuildConfig] = Field(
        default_factory=CondaBuildConfig,
        exclude=True,  # Will not be rendered in the model dump
        description="""
        Settings in this block are used to control how ``conda build``
        runs and produces artifacts. An example of the such configuration is:

        .. code-block:: yaml

            conda_build:
                pkg_format: 2
                zstd_compression_level: 16
                error_overlinking: False

        """,
    )

    conda_build_tool: Optional[conda_build_tools] = Field(
        default="conda-build",
        description="""
        Use this option to choose which tool is used to build your recipe.
        """,
    )

    conda_install_tool: Optional[Literal["conda", "mamba"]] = Field(
        default="mamba",
        description="""
        Use this option to choose which tool is used to provision the tooling in your
        feedstock.
        """,
    )

    conda_forge_output_validation: Optional[bool] = Field(
        default=False,
        description="""
        This field must be set to ``True`` for feedstocks in the ``conda-forge`` GitHub
        organization. It enables the required feedstock artifact validation as described
        in :ref: Output Validation and Feedstock Tokens </maintainer/infrastructure#output-validation>.
        """,
    )

    conda_solver: Optional[
        Union[Literal["libmamba", "classic"], Nullable]
    ] = Field(
        default="libmamba",
        description="""
        Choose which ``conda`` solver plugin to use for feedstock builds.
        """,
    )

    github: Optional[GithubConfig] = Field(
        default_factory=GithubConfig,
        description="""
        Mapping for GitHub-specific configuration options. The defaults are as follows:

        .. code-block:: yaml

            github:
                user_or_org: conda-forge
                repo_name: "my_repo"
                branch_name: main
                tooling_branch_name: main
        """,
    )

    bot: Optional[BotConfig] = Field(
        default_factory=BotConfig,
        description="""
        This dictates the behavior of the conda-forge auto-tick bot which issues
        automatic version updates/migrations for feedstocks.
        A valid example is:

        .. code-block:: yaml

            bot:
                # can the bot automerge PRs it makes on this feedstock
                automerge: true

                # only open PRs if resulting environment is solvable, useful for tightly coupled packages
                check_solvable: true

                # The bot.inspection key in the conda-forge.yml can have one of six possible values:
                inspection: hint-all  # generate hints using all methods

                # any branches listed in this section will get bot migration PRs in addition
                # to the default branch
                abi_migration_branches:
                    - v1.10.x

                version_updates:
                    # use this for packages that are updated too frequently
                    random_fraction_to_keep: 0.1  # keeps 10% of versions at random

        The ``abi_migration_branches`` feature is useful to, for example, add a
        long-term support (LTS) branch for a package.
        """,
    )

    build_platform: Optional[
        PydanticModelGenerator(Platforms, Platforms, "build_platform")()
    ] = Field(
        default_factory=lambda: {
            platform.value: platform.value
            for platform in Platforms
            if not platform.value == "osx_arm64"
        },
        description="""
        This is a mapping from the target platform to the build platform for the
        package to be built. For example, the following builds a ``osx-64`` package
        on the ``linux-64`` build platform using cross-compiling.

        .. code-block:: yaml

            build_platform:
                osx_64: linux_64

        Leaving this field empty implicitly requests to build a package natively. i.e.

        .. code-block:: yaml

            build_platform:
                linux_64: linux_64
                linux_ppc64le: linux_ppc64le
                linux_aarch64: linux_aarch64
                osx_64: osx_64
                osx_arm64: osx_arm64
                win_64: win_64
        """,
    )

    channel_priority: Optional[ChannelPriorityConfig] = Field(
        default="strict",
        exclude=True,  # Will not be rendered in the model dump
        description="""
        The channel priority level for the conda solver during feedstock builds.
        For extra information, see the
        `Strict channel priority <https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-channels.html#strict-channel-priority>`__
        section on conda documentation.
        """,
    )

    choco: Optional[List[str]] = Field(
        default_factory=list,
        description="""
        This parameter allows for conda-smithy to run chocoloatey installs on Windows
        when additional system packages are needed. This is a list of strings that
        represent package names and any additional parameters. For example,

        .. code-block:: yaml

            choco:
                # install a package
                - nvidia-display-driver

                # install a package with a specific version
                - cuda --version=11.0.3

        This is currently only implemented for Azure Pipelines. The command that is run is
        ``choco install {entry} -fdv -y --debug``.  That is, ``choco install`` is executed
        with a standard set of additional flags that are useful on CI.
        """,
    )

    docker: Optional[CondaForgeDocker] = Field(
        default_factory=CondaForgeDocker,
        description="""
        This is a mapping for Docker-specific configuration options.
        Some options are

        .. code-block:: yaml

            docker:
                executable: docker
                image: "condaforge/linux-anvil-comp7"
                command: "bash"
                interactive: True
        """,
    )

    idle_timeout_minutes: Optional[Union[int, Nullable]] = Field(
        default=None,
        description="""
        Configurable idle timeout. Used for packages that don't have chatty enough
        builds. Applicable only to circleci and travis.

        .. code-block:: yaml

            idle_timeout_minutes: 60
        """,
    )

    noarch_platforms: Optional[List[Platforms]] = Field(
        default_factory=lambda: ["linux_64"],
        description="""
        Platforms on which to build noarch packages. The preferred default is a
        single build on ``linux_64``.

        .. code-block:: yaml

            noarch_platforms: linux_64

        To build on multiple platforms, e.g. for simple packages with platform-specific
        dependencies, provide a list.

        .. code-block:: yaml

            noarch_platforms:
            - linux_64
            - win_64
        """,
    )

    os_version: Optional[
        PydanticModelGenerator(Platforms, Union[str, Nullable], "os_version")()
    ] = Field(
        default_factory=lambda: {
            platform.value: None
            for platform in Platforms
            if not (
                platform.value.startswith("osx")
                or platform.value.startswith("win")
            )
        },
        description="""
        This key is used to set the OS versions for `linux_*` platforms. Valid entries
        map a linux platform and arch to either `cos6` or `cos7`.
        Currently `cos6` is the default for `linux-64`.
        All other linux architectures use CentOS 7.
        Here is an example that enables CentOS 7 on ``linux-64`` builds

        .. code-block:: yaml

            os_version:
                linux_64: cos7
        """,
    )

    provider: Optional[
        PydanticModelGenerator(
            Union[Platforms, PlatformsAliases],
            Union[List[CIservices], CIservices, bool, Nullable],
            "provider",
        )()
    ] = Field(
        default_factory=lambda: {
            "linux": None,
            "linux_64": ["azure"],
            "linux_aarch64": None,
            "linux_armv7l": None,
            "linux_ppc64le": None,
            "linux_s390x": None,
            "osx": None,
            "osx_64": ["azure"],
            "win": None,
            "win_64": ["azure"],
        },
        description="""
        The ``provider`` field is a mapping from build platform (not target platform)
        to CI service. It determines which service handles each build platform.
        If a desired build platform is not available with a selected provider
        (either natively or with emulation), the build will be disabled.
        Use the ``build_platform`` field to manually specify cross-compilation when
        no providers offer a desired build platform.

        The following are available as supported build platforms:

        * ``linux_64``
        * ``osx_64``
        * ``win_64``
        * ``linux_aarch64``
        * ``linux_ppc64le``
        * ``linux_s390x``
        * ``linux_armv7l``

        The following CI services are available:

        * ``azure``
        * ``circle``
        * ``travis``
        * ``appveyor``
        * ``None`` or ``False`` to disable a build platform.
        * ``default`` to choose an appropriate CI (only if available)

        For example, switching linux_64 & osx_64 to build on Travis CI, with win_64 on
        Appveyor:

        .. code-block:: yaml

            provider:
                linux_64: travis
                osx_64: travis
                win_64: appveyor

        Currently, x86_64 platforms are enabled, but other build platforms are
        disabled by default. i.e. an empty provider entry is equivalent to the
        following:

        .. code-block:: yaml

            provider:
                linux_64: azure
                osx_64: azure
                win_64: azure
                linux_ppc64le: None
                linux_aarch64: None

        To enable ``linux_ppc64le`` and ``linux_aarch64`` add the following:

        .. code-block:: yaml

            provider:
                linux_ppc64le: default
                linux_aarch64: default
        """,
    )

    package: Optional[Union[str, Nullable]] = Field(
        default=None,
        exclude=True,  # Will not be rendered in the model dump
        description="Default location for a package feedstock directory basename.",
    )

    recipe_dir: Optional[str] = Field(
        default="recipe",
        description="""
        The relative path to the recipe directory. The default is:

        .. code-block:: yaml

            recipe_dir: recipe
        """,
    )

    remote_ci_setup: Optional[List[str]] = Field(
        default_factory=lambda: ["conda-forge-ci-setup=4"],
        description="""
        This option can be used to override the default ``conda-forge-ci-setup`` package.
        Can be given with ``${url or channel_alias}::package_name``,
        defaults to conda-forge channel_alias if no prefix is given.

        .. code-block:: yaml

            remote_ci_setup: "conda-forge-ci-setup=4"
        """,
    )

    shellcheck: Optional[Union[ShellCheck, Nullable]] = Field(
        default=None,
        exclude=True,  # Will not be rendered in the model dump
        description="""
        Shell scripts used for builds or activation scripts can be linted with
        shellcheck. This option can be used to enable shellcheck and configure
        its behavior. This is not enabled by default, but can be enabled like so:

        .. code-block:: yaml

            shellcheck:
                enabled: True

        """,
    )

    skip_render: Optional[List[BotConfigSkipRenderChoices]] = Field(
        default_factory=list,
        description="""
        This option specifies a list of files which ``conda smithy`` will skip rendering.
        This is useful for files that are not templates, but are still in the recipe
        directory. The default value is an empty list [ ], which will consider that
        all files can be rendered. For example, if you want to skip rendering
        the .gitignore and LICENSE.txt files, you can add the following:

        .. code-block:: yaml

            skip_render:
                - .gitignore
                - LICENSE.txt
        """,
    )

    templates: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="""
        This is mostly an internal field for specifying where template files reside.
        You shouldn't need to modify it.
        """,
    )

    test_on_native_only: Optional[bool] = Field(
        default=False,
        description="""
        This was used for disabling testing for cross-compiling.

        .. note::
            This has been deprecated in favor of the top-level ``test`` field.
            It is now mapped to ``test: native_and_emulated``.
        """,
    )

    test: Optional[Union[DefaultTestPlatforms, Nullable]] = Field(
        default=None,
        description="""
        This is used to configure on which platforms a recipe is tested.

        .. code-block:: yaml

            test: native_and_emulated

        Will do testing only if the platform is native or if there is an emulator.

        .. code-block:: yaml

            test: native

        Will do testing only if the platform is native.
        """,
    )

    upload_on_branch: Optional[Union[str, Nullable]] = Field(
        default=None,
        exclude=True,  # Will not be rendered in the model dump
        description="""
        This parameter restricts uploading access on work from certain branches of the
        same repo. Only the branch listed in ``upload_on_branch`` will trigger uploading
        of packages to the target channel. The default is to skip this check if the key
        ``upload_on_branch`` is not in ``conda-forge.yml``. To restrict uploads to the
        main branch:

        .. code-block:: yaml

            upload_on_branch: main
        """,
    )

    config_version: Optional[str] = Field(
        default="2",
        description="""
        The version of the ``conda-forge.yml`` specification.
        This should not be manually modified.
        """,
    )

    exclusive_config_file: Optional[Union[str, Nullable]] = Field(
        default=None,
        exclude=True,  # Will not be rendered in the model dump
        description="""
        Exclusive conda-build config file to replace ``conda-forge-pinning``.
        For advanced usage only.
        """,
    )

    compiler_stack: Optional[str] = Field(
        default="comp7",
        description="""
        Compiler stack environment variable. This is used to specify the compiler
        stack to use for builds.

        .. code-block:: yaml

            compiler_stack: comp7
        """,
    )

    min_py_ver: Optional[str] = Field(
        default="27",
        description="""
        Minimum Python version. This is used to specify the minimum Python version
        to use for builds.

        .. code-block:: yaml

            min_py_ver: 27
        """,
    )

    max_py_ver: Optional[str] = Field(
        default="37",
        description="""
        Maximum Python version. This is used to specify the maximum Python version
        to use for builds.

        .. code-block:: yaml

            max_py_ver: 37
        """,
    )

    min_r_ver: Optional[str] = Field(
        default="34",
        description="""
        Minimum R version. This is used to specify the minimum R version to
        use for builds.

        .. code-block:: yaml

            min_r_ver: 34
        """,
    )

    max_r_ver: Optional[str] = Field(
        default="34",
        description="""
        Maximum R version. This is used to specify the maximum R version to use
        for builds.

        .. code-block:: yaml

            max_r_ver: 34
        """,
    )

    private_upload: Optional[bool] = Field(
        default=False,
        description="""
        Whether to upload to a private channel.

        .. code-block:: yaml

            private_upload: False
        """,
    )

    secrets: Optional[List[str]] = Field(
        default_factory=list,
        description="""
        List of secrets to be used in GitHub Actions.
        The default is an empty list and will not be used.
        """,
    )

    clone_depth: Optional[Union[int, Nullable]] = Field(
        default=None,
        description="""
        The depth of the git clone.
        """,
    )

    timeout_minutes: Optional[Union[int, Nullable]] = Field(
        default=None,
        exclude=True,  # Will not be rendered in the model dump
        description="""
        The timeout in minutes for all platforms CI jobs.
        If passed alongside with Azure, it will be used as the default
        timeout for Azure Pipelines jobs.
        """,
    )

    ###################################
    ####       CI Providers        ####
    ###################################
    travis: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="""
        Travis CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """,
    )

    circle: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="""
        Circle CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """,
    )

    appveyor: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"image": "Visual Studio 2017"},
        description="""
        AppVeyor CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """,
    )

    azure: Optional[AzureConfig] = Field(
        default_factory=AzureConfig,
        description="""
        Azure Pipelines CI settings. This is usually read-only and should not
        normally be manually modified. Tools like conda-smithy may modify this, as needed.
        For example:

        .. code-block:: yaml

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


        .. _self-hosted_azure-config:

        Below is an example configuration for setting up a self-hosted Azure agent for Linux:

        .. code-block:: yaml

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

        Below is an example configuration for adding a swapfile on an Azure agent for Linux:

        .. code-block:: yaml

            azure:
                settings_linux:
                    swapfile_size: 10GiB
        """,
    )

    drone: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="""
        Drone CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """,
    )

    github_actions: Optional[GithubActionsConfig] = Field(
        default_factory=GithubActionsConfig,
        description="""
        GitHub Actions CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """,
    )

    woodpecker: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="""
        Woodpecker CI settings. This is usually read-only and should not normally be
        manually modified. Tools like conda-smithy may modify this, as needed.
        """,
    )

    ###################################
    ####       Deprecated          ####
    ###################################

    # Deprecated values, only present for validation will not show up in
    # the model dump, due to exclude=True

    build_with_mambabuild: Optional[bool] = Field(
        default=True,
        exclude=True,
        description="""
        build_with_mambabuild is deprecated, use conda_build_tool instead. Configures the conda-forge CI to run a debug build using the ``mamba`` solver.
        More information can be found in the
        `mamba docs <https://conda-forge.org/docs/maintainer/maintainer_faq.html#mfaq-mamba-local>`__.

        .. code-block:: yaml

            build_with_mambabuild:
            True
        """,
    )

    matrix: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        exclude=True,
        description="""
        Build matrices were used to specify a set of build configurations to run for each
        package pinned dependency. This has been deprecated in favor of the provider field.
        More information can be found in the
        :ref:`Build Matrices </maintainer/knowledge_base#build-matrices>` section of the
        conda-forge docs.
        """,
    )


if __name__ == "__main__":
    from pathlib import Path

    # This is used to generate the model dump for conda-smithy internal use
    # and for documentation purposes.

    model = ConfigModel()

    CONDA_FORGE_DATA = Path(__file__).parent / "data"
    CONDA_FORGE_DATA.mkdir(parents=True, exist_ok=True)
    CONDA_FORGE_JSON = (
        CONDA_FORGE_DATA / f"conda-forge.v{model.config_version}.json"
    )

    with CONDA_FORGE_JSON.open(mode="w+") as f:
        f.write(model.schema_json(indent=2))
        f.write("\n")

    CONDA_FORGE_YML = (
        CONDA_FORGE_DATA / f"conda-forge.v{model.config_version}.yml"
    )
    with CONDA_FORGE_YML.open(mode="w+") as f:
        f.write(yaml.dump(model.dict(), indent=2))
