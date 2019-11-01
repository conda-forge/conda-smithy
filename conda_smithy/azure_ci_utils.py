import os
import typing
import warnings

from msrest.authentication import Authentication, BasicAuthentication
from vsts.build.v4_1.build_client import BuildClient
from vsts.build.v4_1.models import (
    BuildDefinition,
    BuildDefinitionReference,
    SourceRepositories,
    SourceRepository,
)
from vsts.service_endpoint.v4_1.models import ServiceEndpoint
from vsts.service_endpoint.v4_1.service_endpoint_client import (
    ServiceEndpointClient,
)
from vsts.task_agent.v4_0.models import TaskAgentQueue
from vsts.task_agent.v4_0.task_agent_client import TaskAgentClient
from vsts.vss_connection import VssConnection


class AzureConfig:

    _default_org = "conda-forge"
    _default_project_name = "feedstock-builds"

    def __init__(
        self, org_or_user=None, project_name=None, team_instance=None
    ):
        self.org_or_user = org_or_user or os.getenv(
            "AZURE_ORG_OR_USER", self._default_org
        )
        # This will only need to be changed if you need to point to a non-standard azure
        # instance.
        self.instance_base_url = team_instance or os.getenv(
            "AZURE_INSTANCE", f"https://dev.azure.com/{self.org_or_user}"
        )
        self.project_name = project_name or os.getenv(
            "AZURE_PROJECT_NAME", self._default_project_name
        )

        try:
            with open(
                os.path.expanduser("~/.conda-smithy/azure.token"), "r"
            ) as fh:
                self.token = fh.read().strip()
            if not self.token:
                raise ValueError()
        except (IOError, ValueError):
            self.token = None

        # By default for now don't report on the build information back to github
        self.azure_report_build_status = os.getenv(
            "AZURE_REPORT_BUILD_STATUS", "true"
        )

    @property
    def connection(self):
        connection = VssConnection(
            base_url=self.instance_base_url, creds=self.credentials
        )
        return connection

    @property
    def credentials(self):
        if self.token:
            return BasicAuthentication("", self.token)
        else:
            warnings.warn(
                "No token available.  No modifications will be possible!"
            )
            return Authentication()


default_config = AzureConfig()


def get_service_endpoint(config: AzureConfig = default_config):
    service_endpoint_client = ServiceEndpointClient(
        base_url=config.instance_base_url, creds=config.credentials
    )
    endpoints: typing.List[
        ServiceEndpoint
    ] = service_endpoint_client.get_service_endpoints(
        project=config.project_name, type="GitHub"
    )
    for service_endpoint in endpoints:
        if service_endpoint.name == config.org_or_user:
            return service_endpoint
    else:
        raise KeyError("Service endpoint not found")


def get_queues(
    config: AzureConfig = default_config,
) -> typing.List[TaskAgentQueue]:
    aclient = TaskAgentClient(config.instance_base_url, config.credentials)
    return aclient.get_agent_queues(config.project_name)


def get_default_queue(project_name):
    queues = get_queues(project_name)
    for q in queues:
        if q.name == "Default":
            return q
    else:
        raise ValueError("Default queue not found")


def get_repo_reference(config: AzureConfig, github_org, repo_name):
    service_endpoint = get_service_endpoint(config)
    bclient: BuildClient = config.connection.get_client(
        "vsts.build.v4_1.build_client.BuildClient"
    )
    repos: SourceRepositories = bclient.list_repositories(
        project=config.project_name,
        provider_name="github",
        repository=f"{github_org}/{repo_name}",
        service_endpoint_id=service_endpoint.id,
    )

    repo: SourceRepository = repos.repositories[0]
    return repo


def register_repo(github_org, repo_name, config: AzureConfig = default_config):
    from vsts.build.v4_1.models import (
        BuildDefinition,
        BuildDefinitionReference,
        BuildRepository,
    )
    from vsts.task_agent.v4_0.task_agent_client import TaskAgentClient
    import inspect

    bclient = build_client()
    aclient = TaskAgentClient(config.instance_base_url, config.credentials)

    source_repo = get_repo_reference(config, github_org, repo_name)

    new_repo = BuildRepository(
        type="GitHub",
        url=source_repo.properties["cloneUrl"],
        **{
            k: v
            for k, v in source_repo.as_dict().items()
            if k in set(inspect.getfullargspec(BuildRepository).args) - {"url"}
        },
    )
    new_repo.name = source_repo.properties["fullName"]
    new_repo.properties["cleanOptions"] = "0"
    new_repo.properties["skipSyncSource"] = "false"
    new_repo.properties["gitLfsSupport"] = "false"
    new_repo.properties["checkoutNestedSubmodules"] = "false"
    new_repo.properties["labelSources"] = "0"
    new_repo.properties["fetchDepth"] = "0"
    new_repo.properties["labelSourcesFormat"] = "$(build.buildNumber)"
    new_repo.properties["reportBuildStatus"] = config.azure_report_build_status
    new_repo.clean = False

    queues = get_queues(config)
    default_queue = get_default_queue(config)
    service_endpoint = get_service_endpoint(config)

    build_definition = BuildDefinition(
        process={
            "type": 2,
            # These might be optional;
            "resources": {
                "queues": [{"id": q.id, "alias": q.name} for q in queues],
                "endpoints": [
                    {"id": service_endpoint.id, "alias": service_endpoint.name}
                ],
            },
            "yamlFilename": "/azure-pipelines.yml",
        },
        # queue works
        queue=default_queue,
        # now onto this
        repository=new_repo,
        name=repo_name,
        # configure trigger for our builds.
        triggers=[
            {
                "branchFilters": ["+*"],
                "forks": {"enabled": True, "allowSecrets": False},
                "pathFilters": [],
                "isCommentRequiredForPullRequest": False,
                "triggerType": "pullRequest",
            },
            {
                "branchFilters": ["+*"],
                "pathFilters": [],
                "batchChanges": False,
                "maxConcurrentBuildsPerBranch": 1,
                "pollingInterval": 0,
                "triggerType": "continuousIntegration",
            },
        ],
        variable_groups=aclient.get_variable_groups(
            project=config.project_name, group_name="anaconda-org"
        ),
        type="build",
    )

    # clean up existing builds for the same feedstock if present
    existing_definitions: typing.List[
        BuildDefinitionReference
    ] = bclient.get_definitions(project=config.project_name, name=repo_name)
    if existing_definitions:
        assert len(existing_definitions) == 1
        ed = existing_definitions[0]
        bclient.update_definition(
            definition=build_definition,
            definition_id=ed.id,
            project=ed.project.name,
        )
    else:
        bclient.create_definition(
            definition=build_definition, project=config.project_name
        )


def build_client(config: AzureConfig = default_config) -> BuildClient:
    return config.connection.get_client(
        "vsts.build.v4_1.build_client.BuildClient"
    )


def repo_registered(
    github_org: str, repo_name: str, config: AzureConfig = default_config
) -> bool:
    existing_definitions: typing.List[BuildDefinitionReference] = build_client(
        config
    ).get_definitions(project=config.project_name, name=repo_name)

    return bool(existing_definitions)


def enable_reporting(repo, config: AzureConfig = default_config) -> None:
    bclient = build_client(config)
    bdef_header = bclient.get_definitions(
        project=config.project_name, name=repo
    )[0]
    bdef = bclient.get_definition(bdef_header.id, bdef_header.project.name)
    bdef.repository.properties["reportBuildStatus"] = "true"
    bclient.update_definition(bdef, bdef.id, bdef.project.name)


def get_build_id(repo, config: AzureConfig = default_config) -> dict:
    """Get the necessary build information to persist in the config file to allow rendering
    of badges.
    This is needed by non-conda-forge use cases"""
    bclient = build_client(config)
    bdef_header = bclient.get_definitions(
        project=config.project_name, name=repo
    )[0]
    bdef: BuildDefinition = bclient.get_definition(
        bdef_header.id, bdef_header.project.name
    )

    return dict(
        user_or_org=config.org_or_user,
        project_name=config.project_name,
        build_id=bdef.id,
        project_id=bdef.project.id,
    )
