import requests

from .utils import update_conda_forge_config
from .ci_register import (
    circle_token,
    drone_session,
    appveyor_token,
    travis_headers,
    travis_get_repo_info,
    travis_endpoint,
)


def add_feedstock_token_to_circle(user, project, feedstock_token):
    url_template = (
        "https://circleci.com/api/v1.1/project/github/{user}/{project}/envvar?"
        "circle-token={token}"
    )
    url = url_template.format(token=circle_token, user=user, project=project)
    data = {"name": "FEEDSTOCK_TOKEN", "value": feedstock_token}
    response = requests.post(url, data)
    if response.status_code != 201:
        raise ValueError(response)


def add_feedstock_token_to_drone(user, project, feedstock_token):
    session = drone_session()
    response = session.post(
        f"/api/repos/{user}/{project}/secrets",
        json={
            "name": "FEEDSTOCK_TOKEN",
            "data": feedstock_token,
            "pull_request": False,
        },
    )
    if response.status_code != 200:
        # Check that the token is in secrets already
        session = drone_session()
        response2 = session.get(f"/api/repos/{user}/{project}/secrets")
        response2.raise_for_status()
        for secret in response2.json():
            if "FEEDSTOCK_TOKEN" == secret["name"]:
                return
    response.raise_for_status()


def appveyor_encrypt_feedstock_token(feedstock_directory, user, project, feedstock_token):
    headers = {"Authorization": "Bearer {}".format(appveyor_token)}
    url = "https://ci.appveyor.com/api/account/encrypt"
    response = requests.post(
        url, headers=headers, data={"plainValue": feedstock_token}
    )
    if response.status_code != 200:
        raise ValueError(response)

    with update_conda_forge_config(feedstock_directory) as code:
        code.setdefault("appveyor", {}).setdefault("secure", {})[
            "FEEDSTOCK_TOKEN"
        ] = response.content.decode("utf-8")


def add_feedstock_token_to_travis(user, project, feedstock_token):
    """Add the FEEDSTOCK_TOKEN to travis."""

    headers = travis_headers()

    repo_info = travis_get_repo_info(user, project)
    repo_id = repo_info["id"]

    data = {
        "env_var.name": "FEEDSTOCK_TOKEN",
        "env_var.value": feedstock_token,
        "env_var.public": "false",
    }
    r = requests.post(
        "{}/repo/{repo_id}/env_vars".format(travis_endpoint, repo_id=repo_id),
        headers=headers,
        json=data,
    )
    if r.status_code != 201:
        r.raise_for_status()


def add_feedstock_token_to_azure(user, project, feedstock_token):
    from .azure_ci_utils import build_client
    from .azure_ci_utils import default_config as config
    from vsts.build.v4_1.models import BuildDefinitionVariable
    bclient = build_client()

    existing_definitions = bclient.get_definitions(project=config.project_name, name=project)
    if existing_definitions:
        assert len(existing_definitions) == 1
        ed = existing_definitions[0]
    else:
        raise RuntimeError(
            "Cannot add FEEDSTOCK_TOKEN to a repo that is not already registered on azure CI!")

    if ed.variables is None:
        ed.variables = {}

    ed.variables["FEEDSTOCK_TOKEN"] = BuildDefinitionVariable(
        allow_override=False,
        is_secret=True,
        value=feedstock_token,
    )

    bclient.update_definition(
        definition=ed,
        definition_id=ed.id,
        project=ed.project.name,
    )
