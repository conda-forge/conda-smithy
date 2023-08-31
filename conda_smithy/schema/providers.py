from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


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

    timeout_minutes: int = Field(
        default=None,
        description="The maximum amount of time (in minutes) that a job can run before it is automatically canceled",
    )

    force: bool = Field(
        default=False,
        description="Force building all supported providers",
    )

    # toggle for storing the conda build_artifacts directory (including the
    # built packages) as an Azure pipeline artifact that can be downloaded
    store_build_artifacts: bool = Field(
        default=False,
        description="Store the conda build_artifacts directory as an Azure pipeline artifact",
    )

    # toggle for freeing up some extra space on the default Azure Pipelines
    # linux image before running the Docker container for building
    free_disk_space: bool = Field(
        default=False,
        description="Free up disk space",
    )

    # limit the amount of CI jobs running concurrently at a given time
    # each OS will get its proportional share of the configured value
    max_parallel: int = Field(
        default=50,
        description="Limit the amount of CI jobs running concurrently at a given time",
    )

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
