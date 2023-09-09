from enum import Enum
from typing import Dict, Optional, Union

from pydantic import BaseModel, Field


class AzureSelfHostedRunnerSettings(BaseModel):
    """This is the settings for self-hosted runners."""

    pool: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="The pool of self-hosted runners, e.g. 'vmImage': 'ubuntu-latest'",
    )
    timeoutInMinutes: Optional[int] = Field(
        default=360, description="Timeout in minutes"
    )
    variables: Optional[Dict[str, str]] = Field(
        default=None, description="Variables"
    )


class AzureConfig(BaseModel):
    """
    This dictates the behavior of the Azure Pipelines CI service. It is a sub-mapping for Azure-specific configuration options. For more information and some variables specifications, see the [Azure Pipelines schema reference documentation](https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/?view=azure-pipelines).
    """

    project_name: Optional[str] = Field(
        default="feedstock-builds",
        description="The name of the Azure Pipelines project",
    )

    project_id: Optional[str] = Field(
        default="84710dde-1620-425b-80d0-4cf5baca359d",  # shouldn't this be an environment variable?
        description="The ID of the Azure Pipelines project",
    )

    user_or_org: Optional[str] = Field(
        default="conda-forge",
        description="The name of the GitHub user or organization, if passed with the GithubConfig provider, must comply with the value of the user_or_org field",
    )

    timeout_minutes: Optional[Union[int, None]] = Field(
        default=None,
        description="The maximum amount of time (in minutes) that a job can run before it is automatically canceled",
    )

    force: Optional[bool] = Field(
        default=False,
        description="Force building all supported providers",
    )

    # toggle for storing the conda build_artifacts directory (including the
    # built packages) as an Azure pipeline artifact that can be downloaded
    store_build_artifacts: Optional[bool] = Field(
        default=False,
        description="Store the conda build_artifacts directory as an Azure pipeline artifact",
    )

    # toggle for freeing up some extra space on the default Azure Pipelines
    # linux image before running the Docker container for building
    free_disk_space: Optional[bool] = Field(
        default=False,
        description="Free up disk space",
    )

    # limit the amount of CI jobs running concurrently at a given time
    # each OS will get its proportional share of the configured value
    max_parallel: Optional[int] = Field(
        default=50,
        description="Limit the amount of CI jobs running concurrently at a given time",
    )

    # Self-hosted runners specific configuration
    settings_linux: AzureSelfHostedRunnerSettings = Field(
        default_factory=lambda: AzureSelfHostedRunnerSettings(),
        description="Linux-specific settings for self-hosted runners",
    )

    settings_osx: AzureSelfHostedRunnerSettings = Field(
        default_factory=lambda: AzureSelfHostedRunnerSettings(),
        description="OSX-specific settings for self-hosted runners",
    )

    settings_win: AzureSelfHostedRunnerSettings = Field(
        default_factory=lambda: AzureSelfHostedRunnerSettings(),
        description="Windows-specific settings for self-hosted runners",
    )


class GithubConfig(BaseModel):
    user_or_org: Optional[str] = Field(
        description="The name of the GitHub user or organization, if passed with the AzureConfig provider, must comply with the value of the user_or_org field",
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
        description="The name of the branch to use for rerender+webservices github actions and conda-forge-ci-setup-feedstock references",
        default="main",
    )


class CondaBuildTools(str, Enum):
    conda_build = "conda-build"
    conda_build_classic = "conda-build+classic"
    conda_build_mamba = "conda-build+conda-libmamba-solver"
    mambabuild = "mambabuild"


class CIservices(str, Enum):
    azure = "azure"
    circle = "circle"
    travis = "travis"
    appveyor = "appveyor"
    default = "default"
