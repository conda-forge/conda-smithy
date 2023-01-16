"""This module generates and registers feedstock tokens.

A feedstock_token is a unique token given to each feedstock that allows it
to execute copies of outputs from a staging conda channel to a production channel.

The correct way to use this module is to call its functions via the command
line utility. The relevant functions are

    conda-smithy generate-feedstock-token
    conda-smithy register-feedstock-token

The `generate-feedstock-token` command must be called before the `register-feedstock-token`
command. It generates a random token and writes it to

    ~/.conda-smithy/{user or org}_{ci service}_{repo}.token

Then when you call `register-feedstock-token`, the generated token is placed
as a secret variable on the CI services. The code will generate a unique token for
each CI service for a feedstock. In order to enable token rotations, multiple
tokens are allowed per feedstock-CI combination. The token hashed using `scrypt` and
then uploaded to the token registry (a repo on GitHub).
"""

import os
import json
import sys
import secrets
import hmac
import base64
from contextlib import redirect_stderr, redirect_stdout

import requests
import scrypt


def feedstock_token_local_path(user, project, ci=None):
    """Return the path locally where the feedstock
    token is stored.
    """
    if ci is None:
        pth = os.path.join(
            "~",
            ".conda-smithy",
            "%s_%s.token" % (user, project),
        )
    else:
        pth = os.path.join(
            "~",
            ".conda-smithy",
            "%s_%s_%s.token" % (user, ci, project),
        )
    return os.path.expanduser(pth)


def generate_and_write_feedstock_token(user, project, ci=None):
    """Generate a feedstock token and write it to

        ~/.conda-smithy/{user or org}_{repo}.token

    This function will fail if the token file already exists.
    """
    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    failed = False
    err_msg = None
    with open(os.devnull, "w") as fp, redirect_stdout(fp), redirect_stderr(fp):
        try:
            token = secrets.token_hex(32)
            pth = feedstock_token_local_path(user, project, ci=ci)
            if os.path.exists(pth):
                failed = True
                err_msg = (
                    "Token for %s/%s on CI%s is already written locally!"
                    % (
                        user,
                        project,
                        "" if ci is None else " " + ci,
                    )
                )
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
                    "Generating the feedstock token for %s/%s on CI%s failed!"
                    " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
                    " defined in the environment to investigate!"
                )
                % (user, project, "" if ci is None else " " + ci)
            )

    return failed


def read_feedstock_token(user, project, ci=None):
    """Read the feedstock token from

        ~/.conda-smithy/{user or org}_{repo}.token

    In order to not spill any tokens to stdout/stderr, this function
    should be used in a `try...except` block with stdout/stderr redirected
    to /dev/null, etc.
    """
    err_msg = None
    feedstock_token = None

    # read the token
    user_token_pth = feedstock_token_local_path(user, project, ci=ci)

    if not os.path.exists(user_token_pth):
        err_msg = "No token found in '%s'" % user_token_pth
    else:
        with open(user_token_pth, "r") as fp:
            feedstock_token = fp.read().strip()
        if not feedstock_token:
            err_msg = "Empty token found in '%s'" % user_token_pth
            feedstock_token = None
    return feedstock_token, err_msg


def feedstock_token_repo_path(project, ci=None):
    """Return the path in the repo where the feedstock
    token is stored.
    """
    if ci is not None:
        chars = [c for c in project if c.isalnum()]
        while len(chars) < 3:
            chars.append("z")

        return os.path.join(
            "tokens",
            ci,
            chars[0],
            chars[1],
            chars[2],
            project + ".json",
        )
    else:
        return os.path.join(
            "tokens",
            project + ".json",
        )


def _munge_token_repo(token_repo):
    """convert github urls to the name of the repo"""
    token_repo = token_repo.strip()
    if token_repo.endswith("/"):
        token_repo = token_repo[:-1]
    token_repo = os.path.split(token_repo)[1]
    if token_repo.endswith(".git"):
        token_repo = token_repo[: -len(".git")]
    return token_repo


def _gh_token_api_headers():
    from .github import gh_token

    github_token = gh_token()
    return {
        "Authorization": "Bearer %s" % github_token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def feedstock_token_exists(user, project, token_repo, ci=None):
    """Test if the feedstock token exists for the given repo.

    All exceptions are swallowed and stdout/stderr from this function is
    redirected to `/dev/null`. Sanitized error messages are
    displayed at the end.

    If you need to debug this function, define `DEBUG_FEEDSTOCK_TOKENS` in
    your environment before calling this function.
    """
    token_repo = _munge_token_repo(token_repo)
    token_file = feedstock_token_repo_path(project, ci=ci)

    exists = False
    failed = False
    err_msg = None
    with open(os.devnull, "w") as fp, redirect_stdout(fp), redirect_stderr(fp):
        try:
            r = requests.get(
                "https://api.github.com/repos/%s/"
                "%s/contents/tokens/%s" % (user, token_repo, token_file),
                headers=_gh_token_api_headers(),
            )
            if r.status_code == 200:
                exists = True
            elif r.status_code == 404:
                exists = False
            else:
                err_msg = (
                    "HTTP request for checking if token exists raised %d!"
                    % r.status_code
                )
                r.raise_for_status()
        except Exception as e:
            if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                raise e
            failed = True

    if failed:
        final_err_msg = (
            "Testing for the feedstock token for %s/%s for CI%s failed!"
            " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
            " defined in the environment to investigate!"
        ) % (user, project, "" if ci is None else " " + ci)
        if err_msg:
            final_err_msg += " - error: %s" % err_msg
        raise RuntimeError(err_msg)

    return exists


def is_valid_feedstock_token(
    user, project, feedstock_token, token_repo, ci=None
):
    """Test if the input feedstock_token is valid.

    All exceptions are swallowed and stdout/stderr from this function is
    redirected to `/dev/null`. Sanitized error messages are
    displayed at the end.

    If you need to debug this function, define `DEBUG_FEEDSTOCK_TOKENS` in
    your environment before calling this function.
    """
    token_repo = _munge_token_repo(token_repo)
    token_file = feedstock_token_repo_path(project, ci=ci)

    valid = False
    failed = False
    err_msg = None

    with open(os.devnull, "w") as fp, redirect_stdout(fp), redirect_stderr(fp):
        try:
            r = requests.get(
                "https://api.github.com/repos/%s/"
                "%s/contents/tokens/%s" % (user, token_repo, token_file),
                headers=_gh_token_api_headers(),
            )
            if r.status_code == 200:
                data = r.json()
                assert data["encoding"] == "base64"
                token_data = json.loads(
                    base64.standard_b64decode(data["content"]).decode("utf-8")
                )
                salted_token = scrypt.hash(
                    feedstock_token,
                    bytes.fromhex(token_data["salt"]),
                    buflen=256,
                )
                valid = hmac.compare_digest(
                    salted_token,
                    bytes.fromhex(token_data["hashed_token"]),
                )
            elif r.status_code == 404:
                valid = False
            else:
                valid = False
                err_msg = (
                    "HTTP request for validating token raised %d!"
                    % r.status_code
                )
                r.raise_for_status()
        except Exception as e:
            if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                raise e
            failed = True

    if failed:
        valid = False
        final_err_msg = (
            "Validating feedstock token for %s/%s for CI%s failed!"
            " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
            " defined in the environment to investigate!"
        ) % (user, project, "" if ci is None else " " + ci)
        if err_msg:
            final_err_msg += " - error: %s" % err_msg
        raise RuntimeError(err_msg)

    return valid


def register_feedstock_token(user, project, token_repo, ci=None, append=False):
    """Register the feedstock token with the token repo.

    This function uses a random salt and scrypt to hash the feedstock
    token before writing it to the token repo. NEVER STORE THESE TOKENS
    IN PLAIN TEXT!

    All exceptions are swallowed and stdout/stderr from this function is
    redirected to `/dev/null`. Sanitized error messages are
    displayed at the end.

    If you need to debug this function, define `DEBUG_FEEDSTOCK_TOKENS` in
    your environment before calling this function.
    """
    token_repo = _munge_token_repo(token_repo)
    token_file = feedstock_token_repo_path(project, ci=ci)

    failed = False
    err_msg = None

    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    with open(os.devnull, "w") as fp, redirect_stdout(fp), redirect_stderr(fp):
        try:
            r = requests.get(
                "https://api.github.com/repos/%s/"
                "%s/contents/tokens/%s" % (user, token_repo, token_file),
                headers=_gh_token_api_headers(),
            )
            if r.status_code == 200:
                if not append:
                    failed = True
                    err_msg = (
                        "Token for repo %s/%s on CI%s already exists!"
                        % (
                            user,
                            project,
                            "" if ci is None else " " + ci,
                        )
                    )
                    raise RuntimeError(err_msg)

                data = r.json()
                assert data["encoding"] == "base64"
                token_data = json.loads(
                    base64.standard_b64decode(data["content"]).decode("utf-8")
                )
            elif r.status_code == 404:
                token_data = {"tokens": []}
                data = None
            else:
                failed = True
                err_msg = "Could not read token for repo %s/%s on CI%s!" % (
                    user,
                    project,
                    "" if ci is None else " " + ci,
                )
                r.raise_for_status()

            # convert to new format
            if "tokens" not in token_data:
                token_data = {"tokens": [token_data]}

            # salt, encrypt and write
            feedstock_token, err_msg = read_feedstock_token(
                user, project, ci=ci
            )
            if err_msg:
                failed = True
                raise RuntimeError(err_msg)
            salt = os.urandom(64)
            salted_token = scrypt.hash(feedstock_token, salt, buflen=256)
            token_data["tokens"].append(
                {
                    "salt": salt.hex(),
                    "hashed_token": salted_token.hex(),
                }
            )

            edata = base64.standard_b64encode(
                json.dumps(token_data).encode("utf-8")
            ).decode("ascii")
            json_data = {
                "message": (
                    "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** "
                    "added token for %s/%s on CI%s"
                    % (user, project, "" if ci is None else " " + ci)
                ),
                "content": edata,
            }
            if data is not None:
                json_data["sha"] = data["sha"]
            r = requests.put(
                "https://api.github.com/repos/%s/"
                "%s/contents/tokens/%s" % (user, token_repo, token_file),
                headers=_gh_token_api_headers(),
                json=json_data,
            )
            if r.status_code != 201:
                failed = True
                err_msg = "Could not write token for repo %s/%s on CI%s!" % (
                    user,
                    project,
                    "" if ci is None else " " + ci,
                )
                r.raise_for_status()

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
                    "Registering the feedstock token for %s/%s on CI%s failed!"
                    " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
                    " defined in the environment to investigate!"
                )
                % (user, project, "" if ci is None else " " + ci)
            )

    return failed


def register_feedstock_token_with_proviers(
    user,
    project,
    *,
    drone=True,
    circle=True,
    travis=True,
    azure=True,
    github_actions=True,
    clobber=True,
    drone_endpoints=(),
    unique_token_per_provider=False,
):
    """Register the feedstock token with provider CI services.

    Note that if a feedstock token is already registered and `clobber=True`
    this function will overwrite existing tokens.

    All exceptions are swallowed and stdout/stderr from this function is
    redirected to `/dev/null`. Sanitized error messages are
    displayed at the end.

    If you need to debug this function, define `DEBUG_FEEDSTOCK_TOKENS` in
    your environment before calling this function.
    """
    # we are swallong all of the logs below, so we do a test import here
    # to generate the proper errors for missing tokens
    from .ci_register import travis_endpoint  # noqa
    from .azure_ci_utils import default_config  # noqa

    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    failed = False
    err_msg = None
    with open(os.devnull, "w") as fp:
        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
            fpo = sys.stdout
            fpe = sys.stdout
        else:
            fpo = fp
            fpe = fp

        with redirect_stdout(fpo), redirect_stderr(fpe):
            try:
                if not unique_token_per_provider:
                    feedstock_token, err_msg = read_feedstock_token(
                        user, project, ci=None
                    )
                    if err_msg:
                        failed = True
                        raise RuntimeError(err_msg)

                if circle:
                    if unique_token_per_provider:
                        feedstock_token, err_msg = read_feedstock_token(
                            user, project, ci="circle"
                        )
                        if err_msg:
                            failed = True
                            raise RuntimeError(err_msg)

                    try:
                        add_feedstock_token_to_circle(
                            user, project, feedstock_token, clobber
                        )
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on circle!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if drone:
                    if unique_token_per_provider:
                        feedstock_token, err_msg = read_feedstock_token(
                            user, project, ci="drone"
                        )
                        if err_msg:
                            failed = True
                            raise RuntimeError(err_msg)

                    for drone_endpoint in drone_endpoints:
                        try:
                            add_feedstock_token_to_drone(
                                user,
                                project,
                                feedstock_token,
                                clobber,
                                drone_endpoint,
                            )
                        except Exception as e:
                            if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                                raise e
                            else:
                                err_msg = (
                                    "Failed to register feedstock token for %s/%s"
                                    " on drone endpoint %s!"
                                ) % (user, project, drone_endpoint)
                                failed = True
                                raise RuntimeError(err_msg)

                if travis:
                    if unique_token_per_provider:
                        feedstock_token, err_msg = read_feedstock_token(
                            user, project, ci="travis"
                        )
                        if err_msg:
                            failed = True
                            raise RuntimeError(err_msg)

                    try:
                        add_feedstock_token_to_travis(
                            user, project, feedstock_token, clobber
                        )
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on travis!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if azure:
                    if unique_token_per_provider:
                        feedstock_token, err_msg = read_feedstock_token(
                            user, project, ci="azure"
                        )
                        if err_msg:
                            failed = True
                            raise RuntimeError(err_msg)
                    try:
                        add_feedstock_token_to_azure(
                            user, project, feedstock_token, clobber
                        )
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on azure!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if github_actions:
                    if unique_token_per_provider:
                        feedstock_token, err_msg = read_feedstock_token(
                            user, project, ci="github_actions"
                        )
                        if err_msg:
                            failed = True
                            raise RuntimeError(err_msg)

                    try:
                        add_feedstock_token_to_github_actions(
                            user, project, feedstock_token, clobber
                        )
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on github actions!"
                            ) % (user, project)
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
                    " defined in the environment to investigate!"
                )
                % (user, project)
            )


def add_feedstock_token_to_circle(user, project, feedstock_token, clobber):
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

    have_feedstock_token = False
    for evar in r.json():
        if evar["name"] == "FEEDSTOCK_TOKEN":
            have_feedstock_token = True

    if have_feedstock_token and clobber:
        r = requests.delete(
            url_template.format(
                token=circle_token,
                user=user,
                project=project,
                extra="/FEEDSTOCK_TOKEN",
            )
        )
        if r.status_code != 200:
            r.raise_for_status()

    if not have_feedstock_token or (have_feedstock_token and clobber):
        data = {"name": "FEEDSTOCK_TOKEN", "value": feedstock_token}
        response = requests.post(
            url_template.format(
                token=circle_token, user=user, project=project, extra=""
            ),
            data,
        )
        if response.status_code != 201:
            raise ValueError(response)


def add_feedstock_token_to_drone(
    user, project, feedstock_token, clobber, drone_endpoint
):
    from .ci_register import drone_session

    session = drone_session(drone_endpoint)

    r = session.get(f"/api/repos/{user}/{project}/secrets")
    r.raise_for_status()
    have_feedstock_token = False
    for secret in r.json():
        if "FEEDSTOCK_TOKEN" == secret["name"]:
            have_feedstock_token = True

    if have_feedstock_token and clobber:
        r = session.patch(
            f"/api/repos/{user}/{project}/secrets/FEEDSTOCK_TOKEN",
            json={"data": feedstock_token, "pull_request": False},
        )
        r.raise_for_status()
    elif not have_feedstock_token:
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


def add_feedstock_token_to_travis(user, project, feedstock_token, clobber):
    """Add the FEEDSTOCK_TOKEN to travis."""
    from .ci_register import (
        travis_endpoint,
        travis_headers,
        travis_get_repo_info,
    )

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

    if have_feedstock_token and clobber:
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
    elif not have_feedstock_token:
        r = requests.post(
            "{}/repo/{repo_id}/env_vars".format(
                travis_endpoint, repo_id=repo_id
            ),
            headers=headers,
            json=data,
        )
        if r.status_code != 201:
            r.raise_for_status()


def add_feedstock_token_to_azure(user, project, feedstock_token, clobber):
    from .azure_ci_utils import build_client, get_default_build_definition
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

    ed = bclient.get_definition(ed.id, project=config.project_name)

    if not hasattr(ed, "variables") or ed.variables is None:
        variables = {}
    else:
        variables = ed.variables

    if "FEEDSTOCK_TOKEN" in variables:
        have_feedstock_token = True
    else:
        have_feedstock_token = False

    if not have_feedstock_token or (have_feedstock_token and clobber):
        variables["FEEDSTOCK_TOKEN"] = BuildDefinitionVariable(
            allow_override=False,
            is_secret=True,
            value=feedstock_token,
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


def add_feedstock_token_to_github_actions(
    user, project, feedstock_token, clobber
):
    from .github import gh_token
    from github import Github

    gh = Github(gh_token())
    repo = gh.get_repo(f"{user}/{project}")

    if not clobber:
        status, headers, data = repo._requester.requestJson(
            "GET", f"{repo.url}/actions/secrets"
        )
        assert status == 200
        data = json.loads(data)
        for secret_data in data["secrets"]:
            if secret_data["name"] == "FEEDSTOCK_TOKEN":
                return

    assert repo.create_secret("FEEDSTOCK_TOKEN", feedstock_token)
