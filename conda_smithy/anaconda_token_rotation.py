"""This module updates/rotates anaconda/binstar tokens.

The correct way to use this module is to call its functions via the command
line utility. The relevant one is

    conda-smithy update-anaconda-token

Note that if you are using appveyor, you will need to push the changes to the
conda-forge.yml in your feedstock to GitHub.
"""

import os
import sys
from contextlib import redirect_stderr, redirect_stdout

import requests
from github import Github

from .utils import update_conda_forge_config


def _get_anaconda_token():
    """use this helper to enable easier patching for tests"""
    try:
        from .ci_register import anaconda_token

        return anaconda_token
    except ImportError:
        raise RuntimeError(
            "You must have the anaconda token defined to do token rotation!"
        )


def rotate_anaconda_token(
    user,
    project,
    feedstock_config_path,
    drone=True,
    circle=True,
    travis=True,
    azure=True,
    appveyor=True,
    github_actions=True,
    token_name="BINSTAR_TOKEN",
    drone_endpoints=(),
):
    """Rotate the anaconda (binstar) token used by the CI providers

    All exceptions are swallowed and stdout/stderr from this function is
    redirected to `/dev/null`. Sanitized error messages are
    displayed at the end.

    If you need to debug this function, define `DEBUG_ANACONDA_TOKENS` in
    your environment before calling this function.
    """
    # we are swallong all of the logs below, so we do a test import here
    # to generate the proper errors for missing tokens
    # note that these imports cover all providers
    from .ci_register import travis_endpoint  # noqa
    from .azure_ci_utils import default_config  # noqa
    from .github import gh_token

    anaconda_token = _get_anaconda_token()

    if github_actions:
        gh = Github(gh_token())

    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    failed = False
    err_msg = None
    with open(os.devnull, "w") as fp:
        if "DEBUG_ANACONDA_TOKENS" in os.environ:
            fpo = sys.stdout
            fpe = sys.stderr
        else:
            fpo = fp
            fpe = fp

        with redirect_stdout(fpo), redirect_stderr(fpe):
            try:
                if circle:
                    try:
                        rotate_token_in_circle(
                            user, project, anaconda_token, token_name
                        )
                    except Exception as e:
                        if "DEBUG_ANACONDA_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to rotate token for %s/%s"
                                " on circle!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if drone:
                    for drone_endpoint in drone_endpoints:
                        try:
                            rotate_token_in_drone(
                                user,
                                project,
                                anaconda_token,
                                token_name,
                                drone_endpoint,
                            )
                        except Exception as e:
                            if "DEBUG_ANACONDA_TOKENS" in os.environ:
                                raise e
                            else:
                                err_msg = (
                                    "Failed to rotate token for %s/%s"
                                    " on drone endpoint %s!"
                                ) % (user, project, drone_endpoint)
                                failed = True
                                raise RuntimeError(err_msg)

                if travis:
                    try:
                        rotate_token_in_travis(
                            user,
                            project,
                            feedstock_config_path,
                            anaconda_token,
                            token_name,
                        )
                    except Exception as e:
                        if "DEBUG_ANACONDA_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to rotate token for %s/%s"
                                " on travis!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if azure:
                    try:
                        rotate_token_in_azure(
                            user, project, anaconda_token, token_name
                        )
                    except Exception as e:
                        if "DEBUG_ANACONDA_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to rotate token for %s/%s" " on azure!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if appveyor:
                    try:
                        rotate_token_in_appveyor(
                            feedstock_config_path, anaconda_token, token_name
                        )
                    except Exception as e:
                        if "DEBUG_ANACONDA_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to rotate token for %s/%s"
                                " on appveyor!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if github_actions:
                    try:
                        rotate_token_in_github_actions(
                            user, project, anaconda_token, token_name, gh
                        )
                    except Exception as e:
                        if "DEBUG_ANACONDA_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to rotate token for %s/%s"
                                " on github actions!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

            except Exception as e:
                if "DEBUG_ANACONDA_TOKENS" in os.environ:
                    raise e
                failed = True

    if failed:
        if err_msg:
            raise RuntimeError(err_msg)
        else:
            raise RuntimeError(
                (
                    "Rotating the feedstock token in providers for %s/%s failed!"
                    " Try the command locally with DEBUG_ANACONDA_TOKENS"
                    " defined in the environment to investigate!"
                )
                % (user, project)
            )


def rotate_token_in_circle(user, project, binstar_token, token_name):
    from .ci_register import circle_token

    url_template = (
        "https://circleci.com/api/v1.1/project/github/{user}/{project}/envvar{extra}?"
        "circle-token={token}"
    )

    r = requests.get(
        url_template.format(
            token=circle_token, user=user, project=project, extra=""
        )
    )
    if r.status_code != 200:
        r.raise_for_status()

    have_binstar_token = False
    for evar in r.json():
        if evar["name"] == token_name:
            have_binstar_token = True

    if have_binstar_token:
        r = requests.delete(
            url_template.format(
                token=circle_token,
                user=user,
                project=project,
                extra="/%s" % token_name,
            )
        )
        if r.status_code != 200:
            r.raise_for_status()

    data = {"name": token_name, "value": binstar_token}
    response = requests.post(
        url_template.format(
            token=circle_token, user=user, project=project, extra=""
        ),
        data,
    )
    if response.status_code != 201:
        raise ValueError(response)


def rotate_token_in_drone(
    user, project, binstar_token, token_name, drone_endpoint
):
    from .ci_register import drone_session

    session = drone_session(drone_endpoint)

    r = session.get(f"/api/repos/{user}/{project}/secrets")
    r.raise_for_status()
    have_binstar_token = False
    for secret in r.json():
        if token_name == secret["name"]:
            have_binstar_token = True

    if have_binstar_token:
        r = session.patch(
            f"/api/repos/{user}/{project}/secrets/{token_name}",
            json={"data": binstar_token, "pull_request": False},
        )
        r.raise_for_status()
    else:
        response = session.post(
            f"/api/repos/{user}/{project}/secrets",
            json={
                "name": token_name,
                "data": binstar_token,
                "pull_request": False,
            },
        )
        if response.status_code != 200:
            response.raise_for_status()


def rotate_token_in_travis(
    user, project, feedstock_config_path, binstar_token, token_name
):
    """update the binstar token in travis."""
    from .ci_register import (
        travis_endpoint,
        travis_get_repo_info,
        travis_headers,
    )

    headers = travis_headers()

    repo_info = travis_get_repo_info(user, project)
    repo_id = repo_info["id"]

    r = requests.get(
        f"{travis_endpoint}/repo/{repo_id}/env_vars",
        headers=headers,
    )
    if r.status_code != 200:
        r.raise_for_status()

    have_binstar_token = False
    ev_id = None
    for ev in r.json()["env_vars"]:
        if ev["name"] == token_name:
            have_binstar_token = True
            ev_id = ev["id"]

    data = {
        "env_var.name": token_name,
        "env_var.value": binstar_token,
        "env_var.public": "false",
    }

    if have_binstar_token:
        r = requests.patch(
            f"{travis_endpoint}/repo/{repo_id}/env_var/{ev_id}",
            headers=headers,
            json=data,
        )
        r.raise_for_status()
    else:
        r = requests.post(
            f"{travis_endpoint}/repo/{repo_id}/env_vars",
            headers=headers,
            json=data,
        )
        if r.status_code != 201:
            r.raise_for_status()

    # we remove the token in the conda-forge.yml since on travis the
    # encrypted values override any value we put in the API
    with update_conda_forge_config(feedstock_config_path) as code:
        if (
            "travis" in code
            and "secure" in code["travis"]
            and token_name in code["travis"]["secure"]
        ):
            del code["travis"]["secure"][token_name]

            if len(code["travis"]["secure"]) == 0:
                del code["travis"]["secure"]

            if len(code["travis"]) == 0:
                del code["travis"]

            print(
                "An old value of the variable %s for travis was found in the "
                "conda-forge.yml. You may need to rerender this feedstock to "
                "use the new value since encrypted secrets inserted in travis.yml "
                "files override those set in the UI/API!"
            )


def rotate_token_in_azure(user, project, binstar_token, token_name):
    from vsts.build.v4_1.models import BuildDefinitionVariable

    from .azure_ci_utils import build_client, get_default_build_definition
    from .azure_ci_utils import default_config as config

    bclient = build_client()

    existing_definitions = bclient.get_definitions(
        project=config.project_name, name=project
    )
    if existing_definitions:
        assert len(existing_definitions) == 1
        ed = existing_definitions[0]
    else:
        raise RuntimeError(
            "Cannot add %s to a repo that is not already registerd on azure CI!"
            % token_name
        )

    ed = bclient.get_definition(ed.id, project=config.project_name)

    if not hasattr(ed, "variables") or ed.variables is None:
        variables = {}
    else:
        variables = ed.variables

    variables[token_name] = BuildDefinitionVariable(
        allow_override=False,
        is_secret=True,
        value=binstar_token,
    )

    build_definition = get_default_build_definition(
        user,
        project,
        config=config,
        variables=variables,
        id=ed.id,
        revision=ed.revision,
    )

    bclient.update_definition(
        definition=build_definition,
        definition_id=ed.id,
        project=ed.project.name,
    )


def rotate_token_in_appveyor(feedstock_config_path, binstar_token, token_name):
    from .ci_register import appveyor_token

    headers = {"Authorization": f"Bearer {appveyor_token}"}
    url = "https://ci.appveyor.com/api/account/encrypt"
    response = requests.post(
        url, headers=headers, data={"plainValue": binstar_token}
    )
    if response.status_code != 200:
        raise ValueError(response)

    with update_conda_forge_config(feedstock_config_path) as code:
        code.setdefault("appveyor", {}).setdefault("secure", {})[
            token_name
        ] = response.content.decode("utf-8")


def rotate_token_in_github_actions(
    user, project, binstar_token, token_name, gh
):
    repo = gh.get_repo(f"{user}/{project}")
    assert repo.create_secret(token_name, binstar_token)
