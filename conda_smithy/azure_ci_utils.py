import os
import typing

from vsts.vss_connection import VssConnection
from msrest.authentication import BasicAuthentication

from vsts.build.v4_1.build_client import BuildClient
from vsts.build.v4_1.models import BuildDefinitionReference
from vsts.build.v4_1.build_client import BuildClient
from vsts.task_agent.v4_0.task_agent_client import TaskAgentClient
from vsts.task_agent.v4_0.models import TaskAgentQueue
from vsts.service_endpoint.v4_1.service_endpoint_client import (
    ServiceEndpointClient
)
from vsts.service_endpoint.v4_1.models import ServiceEndpoint
from vsts.build.v4_1.build_client import BuildClient
from vsts.build.v4_1.models import SourceRepositories, SourceRepository


AZURE_TEAM_INSTANCE = os.getenv(
    "AZURE_INSTANCE", "https://dev.azure.com/conda-forge"
)
AZURE_PROJECT_ID = os.getenv("AZURE_PROJECT_ID", "feedstock-builds")
AZURE_SERVICE_ENDPOINT_NAME = os.getenv(
    "AZURE_SERVICE_ENDPOINT", "conda-forge"
)
# By default for now don't report on the build information back to github
AZURE_REPORT_BUILD_STATUS = os.getenv("AZURE_REPORT_BUILD_STATUS", "false")

try:
    with open(os.path.expanduser("~/.conda-smithy/azure.token"), "r") as fh:
        AZURE_TOKEN = fh.read().strip()
    if not AZURE_TOKEN:
        raise ValueError()
except (IOError, ValueError):
    print(
        "No azure token.  Create a token at https://dev.azure.com/conda-forge/_usersSettings/tokens and\n"
        "put it in ~/.conda-smithy/azure.token"
    )


credentials = BasicAuthentication("", AZURE_TOKEN)
connection = VssConnection(base_url=AZURE_TEAM_INSTANCE, creds=credentials)


def get_service_endpoint(project_id=AZURE_PROJECT_ID):


    service_endpoint_client = ServiceEndpointClient(
        base_url=AZURE_TEAM_INSTANCE, creds=credentials
    )
    endpoints: typing.List[
        ServiceEndpoint
    ] = service_endpoint_client.get_service_endpoints(
        project=project_id, type="GitHub"
    )
    for service_endpoint in endpoints:
        if service_endpoint.name == AZURE_SERVICE_ENDPOINT_NAME:
            return service_endpoint
    else:
        raise KeyError("Service endpoint not found")


def get_queues(project_id=AZURE_PROJECT_ID):
    aclient = TaskAgentClient(AZURE_TEAM_INSTANCE, credentials)
    queues: typing.List[TaskAgentQueue] = aclient.get_agent_queues(project_id)
    return queues


def get_default_queue(project_id):
    queues = get_queues(project_id)
    for q in queues:
        if q.name == "Default":
            return q
    else:
        raise ValueError("Default queue not found")


def get_repo_reference(project_id, github_org, repo_name):


    service_endpoint = get_service_endpoint(project_id)
    bclient: BuildClient = connection.get_client(
        "vsts.build.v4_1.build_client.BuildClient"
    )
    repos: SourceRepositories = bclient.list_repositories(
        project=project_id,
        provider_name="github",
        repository=f"{github_org}/{repo_name}",
        service_endpoint_id=service_endpoint.id,
    )

    repo: SourceRepository = repos.repositories[0]
    return repo


def register_repo(github_org, repo_name, project_id=AZURE_PROJECT_ID):
    from vsts.build.v4_1.models import (
        BuildDefinition,
        BuildDefinitionReference,
        BuildRepository,
    )
    from vsts.task_agent.v4_0.task_agent_client import TaskAgentClient
    import inspect

    bclient = build_client()
    aclient = TaskAgentClient(AZURE_TEAM_INSTANCE, credentials)

    source_repo = get_repo_reference(project_id, github_org, repo_name)

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
    new_repo.properties["reportBuildStatus"] = AZURE_REPORT_BUILD_STATUS
    new_repo.clean = False

    queues = get_queues(project_id)
    default_queue = get_default_queue(project_id)
    service_endpoint = get_service_endpoint(project_id)

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
            project=project_id, group_name="anaconda-org"
        ),
        type="build",
    )

    # clean up existing builds for the same feedstock if present
    existing_definitions: typing.List[
        BuildDefinitionReference
    ] = bclient.get_definitions(project=project_id, name=repo_name)
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
            definition=build_definition, project=project_id
        )


def build_client() -> BuildClient:
    return connection.get_client(
        "vsts.build.v4_1.build_client.BuildClient"
    )


def repo_registered(github_org, repo_name, project_id=AZURE_PROJECT_ID):
    existing_definitions: typing.List[
        BuildDefinitionReference
    ] = build_client().get_definitions(project=project_id, name=repo_name)

    return bool(existing_definitions)


def enable_reporting(user, repo, project_id=AZURE_PROJECT_ID):
    bclient = build_client()
    bdef_header = bclient.get_definitions(project=project_id, name=repo)[0]
    bdef = bclient.get_definition(bdef_header.id, bdef_header.project.name)
    bdef.repository.properties['reportBuildStatus'] = 'true'
    bclient.update_definition(bdef, bdef.id, bdef.project.name)


def get_build_id(user, repo, project_id=AZURE_PROJECT_ID):
    bclient = build_client()
    bdef_header = bclient.get_definitions(
        project=AZURE_PROJECT_ID, name=repo)[0]
    bdef: BuildDefinitionReference = bclient.get_definition(
        bdef_header.id, bdef_header.project.name)
    return bdef.id
