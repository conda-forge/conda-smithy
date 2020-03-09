import tempfile
import os
import json
import secrets
from contextlib import redirect_stderr, redirect_stdout

import git
import requests
import scrypt

from .ci_register import (
    circle_token,
    drone_session,
    travis_headers,
    travis_get_repo_info,
    travis_endpoint,
)
from .github import github_token


def generate_and_write_feedstock_token(user, project):
    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    failed = False
    err_msg = None
    with open(os.devnull, "w") as fp:
        with redirect_stdout(fp), redirect_stderr(fp):
            try:
                token = secrets.token_hex(32)
                pth = os.path.join(
                    "~",
                    ".conda_smithy",
                    "%s_%s_feedstock.token" % (user, project),
                )
                pth = os.path.expanduser(pth)
                if os.path.exists(pth):
                    failed = True
                    err_msg = "Token for %s%s is already written locally!" % (user, project)
                    raise RuntimeError(err_msg)

                os.makedirs(os.path.dirname(pth), exist_ok=True)

                with open(pth, "w") as fp:
                    fp.write(token)
            except Exception as e:
                if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                    raise e
                failed = True

    if failed:
        if err_msg:
            raise RuntimeError(err_msg)
        else:
            raise RuntimeError(
                (
                    "Generating the feedstock token for %s/%s failed!"
                    " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
                    " defined in the environment to investigate!") % (user, project)
                )

    return failed


def read_feedstock_token(user, project):
    err_msg = None
    feedstock_token = None

    # read the token
    user_token_pth = os.path.join(
            "~",
            ".conda_smithy",
            "%s_%s_feedstock.token" % (user, project),
        )
    user_token_pth = os.path.expanduser(user_token_pth)

    if not os.path.exists(user_token_pth):
        err_msg = "No token found in '~/.conda_smithy/%s_%s_feedstock.token'" % (
            user,
            project,
        )
    else:
        with open(user_token_pth, "r") as fp:
            feedstock_token = fp.read().strip()
        if not feedstock_token:
            err_msg = (
                "Empty token found in '~/.conda_smithy/"
                "%s_%s_feedstock.token'"
            ) % (
                user,
                project,
            )
    return feedstock_token, err_msg


def register_feedstock_token(user, project, token_repo):
    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    failed = False
    err_msg = None
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.devnull, "w") as fp:
            with redirect_stdout(fp), redirect_stderr(fp):
                try:
                    feedstock_token, err_msg = read_feedstock_token(user, project)
                    if err_msg:
                        failed = True
                        raise RuntimeError(err_msg)

                    # clone the repo
                    _token_repo = (
                        token_repo
                        .replace("$GITHUB_TOKEN", github_token)
                        .replace("${GITHUB_TOKEN}", github_token)
                        .replace("$GH_TOKEN", github_token)
                        .replace("${GH_TOKEN}", github_token)
                    )
                    repo = git.Repo.clone_from(_token_repo, tmpdir, depth=1)
                    token_file = os.path.join(
                        tmpdir,
                        project.replace("-feedstock", "") + ".json",
                    )

                    # don't overwrite existing tokens
                    if os.path.exists(token_file):
                        failed = True
                        err_msg = "Token for repo %s/%s already exists!" % (user, project)
                        raise RuntimeError(err_msg)

                    # salt, encrypt and write
                    salt = os.urandom(64)
                    maxtime = "0.1"
                    salted_token = scrypt.encrypt(
                        salt,
                        feedstock_token,
                        maxtime=float(maxtime),
                    )
                    data = {
                        "salt": salt,
                        "encrypted_token": salted_token,
                        "maxtime": maxtime,
                    }
                    with open(token_file, "w") as fp:
                        fp.write(json.dump(data))

                    # push
                    repo.index.add(token_file)
                    repo.index.commit("added token for %s/%s" % (user, project))
                    repo.remote().pull(rebase=True)
                    repo.remote().push()
                except Exception as e:
                    if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                        raise e
                    failed = True
    if failed:
        if err_msg:
            raise RuntimeError(err_msg)
        else:
            raise RuntimeError(
                (
                    "Registering the feedstock token for %s/%s failed!"
                    " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
                    " defined in the environment to investigate!") % (user, project)
                )

    return failed


def register_feedstock_token_with_proviers(
        user, project, feedstock_directory,
        drone=True, circle=True,
        travis=True, azure=True
):
    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    failed = False
    err_msg = None
    with open(os.devnull, "w") as fp:
        with redirect_stdout(fp), redirect_stderr(fp):
            try:
                feedstock_token, err_msg = read_feedstock_token(user, project)
                if err_msg:
                    failed = True
                    raise RuntimeError(err_msg)

                if circle:
                    try:
                        add_feedstock_token_to_circle(user, project, feedstock_token)
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on circle!") % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if drone:
                    try:
                        add_feedstock_token_to_drone(user, project, feedstock_token)
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on drone!") % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if travis:
                    try:
                        add_feedstock_token_to_travis(user, project, feedstock_token)
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on travis!") % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if azure:
                    try:
                        add_feedstock_token_to_azure(user, project, feedstock_token)
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on azure!") % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

            except Exception as e:
                if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                    raise e
                failed = True
    if failed:
        if err_msg:
            raise RuntimeError(err_msg)
        else:
            raise RuntimeError(
                (
                    "Registering the feedstock token with proviers for %s/%s failed!"
                    " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
                    " defined in the environment to investigate!") % (user, project)
                )


def add_feedstock_token_to_circle(user, project, feedstock_token):
    url_template = (
        "https://circleci.com/api/v1.1/project/github/{user}/{project}/envvar{extra}?"
        "circle-token={token}"
    )

    r = requests.get(url_template.format(token=circle_token, user=user, project=project, extra=""))
    if r.status_code != 200:
        r.raise_for_status()

    have_feedstock_token = False
    for evar in r.json():
        if evar["name"] == "FEEDSTOCK_TOKEN":
            have_feedstock_token = True

    if have_feedstock_token:
        r = requests.delete(url_template.format(
            token=circle_token,
            user=user,
            project=project,
            extra="FEEDSTOCK_TOKEN",
        ))
        if r.status_code != 200:
            r.raise_for_status()

    data = {"name": "FEEDSTOCK_TOKEN", "value": feedstock_token}
    response = requests.post(
        url_template.format(token=circle_token, user=user, project=project, extra=""),
        data,
    )
    if response.status_code != 201:
        raise ValueError(response)


def add_feedstock_token_to_drone(user, project, feedstock_token):
    session = drone_session()

    r = session.get(f"/api/repos/{user}/{project}/secrets")
    r.raise_for_status()
    have_feedstock_token = False
    for secret in r.json():
        if "FEEDSTOCK_TOKEN" == secret["name"]:
            have_feedstock_token = True

    if have_feedstock_token:
        r = session.patch(
            f"/api/repos/{user}/{project}/secrets/FEEDSTOCK_TOKEN",
            json={
                "data": feedstock_token,
                "pull_request": False,
            },
        )
        r.raise_for_status()
    else:
        response = session.post(
            f"/api/repos/{user}/{project}/secrets",
            json={
                "name": "FEEDSTOCK_TOKEN",
                "data": feedstock_token,
                "pull_request": False,
            },
        )
        if response.status_code != 200:
            response.raise_for_status()


def add_feedstock_token_to_travis(user, project, feedstock_token):
    """Add the FEEDSTOCK_TOKEN to travis."""

    headers = travis_headers()

    repo_info = travis_get_repo_info(user, project)
    repo_id = repo_info["id"]

    r = requests.get(
        "{}/repo/{repo_id}/env_vars".format(travis_endpoint, repo_id=repo_id),
        headers=headers,
    )
    if r.status_code != 200:
        r.raise_for_status()

    have_feedstock_token = False
    ev_id = None
    for ev in r.json()["env_vars"]:
        if ev["name"] == "FEEDSTOCK_TOKEN":
            have_feedstock_token = True
            ev_id = ev["id"]

    data = {
        "env_var.name": "FEEDSTOCK_TOKEN",
        "env_var.value": feedstock_token,
        "env_var.public": "false",
    }

    if have_feedstock_token:
        r = requests.patch(
            "{}/repo/{repo_id}/env_var/{ev_id}".format(
                travis_endpoint,
                repo_id=repo_id,
                ev_id=ev_id,
            ),
            headers=headers,
            json=data,
        )
        r.raise_for_status()
    else:
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

    existing_definitions = bclient.get_definitions(
        project=config.project_name, name=project
    )
    if existing_definitions:
        assert len(existing_definitions) == 1
        ed = existing_definitions[0]
    else:
        raise RuntimeError(
            "Cannot add FEEDSTOCK_TOKEN to a repo that is not already registerd on azure CI!"
        )

    if ed.variables is None:
        ed.variables = {}

    ed.variables["FEEDSTOCK_TOKEN"] = BuildDefinitionVariable(
        allow_override=False, is_secret=True, value=feedstock_token,
    )

    bclient.update_definition(
        definition=ed, definition_id=ed.id, project=ed.project.name,
    )
