"""This module generates and registers feedstock tokens.

A feedstock_token is a unique token given to each feedstock that allows it
to execute copies of outputs from a staging conda channel to a production channel.

The correct way to use this module is to call its functions via the command
line utility. The relevant functions are

    conda-smithy generate-feedstock-token
    conda-smithy register-feedstock-token

The `generate-feedstock-token` command must be called before the `register-feedstock-token`
command. It generates a random token and writes it to

    ~/.conda-smithy/{user or org}_{repo w/o '-feedstock'}_feedstock.token

Then when you call `register-feedstock-token`, the generated token is placed
as a secret variable on the CI services. It is also hashed using `scrypt` and
then uploaded to the token registry (a repo on GitHub).
"""

import tempfile
import os
import json
import sys
import secrets
import hmac
from contextlib import redirect_stderr, redirect_stdout

import git
import requests
import scrypt


def _munge_project(project):
    if project.endswith("-feedstock"):
        return project[:-len("-feedstock")]
    else:
        return project


def generate_and_write_feedstock_token(user, project):
    """Generate a feedstock token and write it to

        ~/.conda-smithy/{user or org}_{repo w/o '-feedstock'}_feedstock.token

    This function will fail if the token file already exists.
    """
    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    failed = False
    err_msg = None
    with open(os.devnull, "w") as fp, redirect_stdout(fp), redirect_stderr(fp):
        try:
            token = secrets.token_hex(32)
            pth = os.path.join(
                "~",
                ".conda-smithy",
                "%s_%s_feedstock.token" % (user, _munge_project(project)),
            )
            pth = os.path.expanduser(pth)
            if os.path.exists(pth):
                failed = True
                err_msg = "Token for %s/%s is already written locally!" % (
                    user,
                    project,
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
                    "Generating the feedstock token for %s/%s failed!"
                    " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
                    " defined in the environment to investigate!"
                )
                % (user, project)
            )

    return failed


def read_feedstock_token(user, project):
    """Read the feedstock token from

        ~/.conda-smithy/{user or org}_{repo w/o '-feedstock'}_feedstock.token

    In order to not spill any tokens to stdout/stderr, this function
    should be used in a `try...except` block with stdout/stderr redirected
    to /dev/null, etc.
    """
    err_msg = None
    feedstock_token = None

    # read the token
    user_token_pth = os.path.join(
        "~", ".conda-smithy", "%s_%s_feedstock.token" % (user, _munge_project(project)),
    )
    user_token_pth = os.path.expanduser(user_token_pth)

    if not os.path.exists(user_token_pth):
        err_msg = (
            "No token found in '~/.conda-smithy/%s_%s_feedstock.token'"
            % (user, _munge_project(project))
        )
    else:
        with open(user_token_pth, "r") as fp:
            feedstock_token = fp.read().strip()
        if not feedstock_token:
            err_msg = (
                "Empty token found in '~/.conda-smithy/"
                "%s_%s_feedstock.token'"
            ) % (user, _munge_project(project))
            feedstock_token = None
    return feedstock_token, err_msg


def feedstock_token_exists(user, project, token_repo):
    """Test if the feedstock token exists for the given repo.

    All exceptions are swallowed and stdout/stderr from this function is
    redirected to `/dev/null`. Sanitized error messages are
    displayed at the end.

    If you need to debug this function, define `DEBUG_FEEDSTOCK_TOKENS` in
    your environment before calling this function.
    """
    from .github import gh_token

    github_token = gh_token()

    exists = False
    failed = False
    err_msg = None
    with tempfile.TemporaryDirectory() as tmpdir, open(
        os.devnull, "w"
    ) as fp, redirect_stdout(fp), redirect_stderr(fp):
        try:
            # clone the repo
            _token_repo = (
                token_repo.replace("$GITHUB_TOKEN", github_token)
                .replace("${GITHUB_TOKEN}", github_token)
                .replace("$GH_TOKEN", github_token)
                .replace("${GH_TOKEN}", github_token)
            )
            git.Repo.clone_from(_token_repo, tmpdir, depth=1)
            token_file = os.path.join(
                tmpdir, "tokens", _munge_project(project) + ".json",
            )

            if os.path.exists(token_file):
                exists = True
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
                    "Testing for the feedstock token for %s/%s failed!"
                    " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
                    " defined in the environment to investigate!"
                )
                % (user, project)
            )

    return exists


def is_valid_feedstock_token(user, project, feedstock_token, token_repo):
    """Test if the input feedstock_token is valid.

    All exceptions are swallowed and stdout/stderr from this function is
    redirected to `/dev/null`. Sanitized error messages are
    displayed at the end.

    If you need to debug this function, define `DEBUG_FEEDSTOCK_TOKENS` in
    your environment before calling this function.
    """
    from .github import gh_token

    github_token = gh_token()

    failed = False
    err_msg = None
    valid = False

    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    with tempfile.TemporaryDirectory() as tmpdir, open(
        os.devnull, "w"
    ) as fp, redirect_stdout(fp), redirect_stderr(fp):
        try:
            # clone the repo
            _token_repo = (
                token_repo.replace("$GITHUB_TOKEN", github_token)
                .replace("${GITHUB_TOKEN}", github_token)
                .replace("$GH_TOKEN", github_token)
                .replace("${GH_TOKEN}", github_token)
            )
            git.Repo.clone_from(_token_repo, tmpdir, depth=1)
            token_file = os.path.join(
                tmpdir, "tokens", _munge_project(project) + ".json",
            )

            # don't overwrite existing tokens
            # check again since there might be a race condition
            if os.path.exists(token_file):
                with open(token_file, "r") as fp:
                    token_data = json.load(fp)

                salted_token = scrypt.hash(
                    feedstock_token,
                    bytes.fromhex(token_data["salt"]),
                    buflen=256,
                )

                valid = hmac.compare_digest(
                    salted_token, bytes.fromhex(token_data["hashed_token"]),
                )
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
                    "Validating the feedstock token for %s/%s failed!"
                    " Try the command locally with DEBUG_FEEDSTOCK_TOKENS"
                    " defined in the environment to investigate!"
                )
                % (user, project)
            )

    return valid


def register_feedstock_token(user, project, token_repo):
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
    from .github import gh_token

    github_token = gh_token()

    failed = False
    err_msg = None

    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    with tempfile.TemporaryDirectory() as tmpdir, open(
        os.devnull, "w"
    ) as fp, redirect_stdout(fp), redirect_stderr(fp):
        try:
            feedstock_token, err_msg = read_feedstock_token(user, project)
            if err_msg:
                failed = True
                raise RuntimeError(err_msg)

            # clone the repo
            _token_repo = (
                token_repo.replace("$GITHUB_TOKEN", github_token)
                .replace("${GITHUB_TOKEN}", github_token)
                .replace("$GH_TOKEN", github_token)
                .replace("${GH_TOKEN}", github_token)
            )
            repo = git.Repo.clone_from(_token_repo, tmpdir, depth=1)
            token_file = os.path.join(
                tmpdir, "tokens", _munge_project(project) + ".json",
            )

            # don't overwrite existing tokens
            # check again since there might be a race condition
            if os.path.exists(token_file):
                failed = True
                err_msg = "Token for repo %s/%s already exists!" % (
                    user,
                    project,
                )
                raise RuntimeError(err_msg)

            # salt, encrypt and write
            salt = os.urandom(64)
            salted_token = scrypt.hash(feedstock_token, salt, buflen=256)
            data = {
                "salt": salt.hex(),
                "hashed_token": salted_token.hex(),
            }
            with open(token_file, "w") as fp:
                json.dump(data, fp)

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
                    " defined in the environment to investigate!"
                )
                % (user, project)
            )

    return failed


def register_feedstock_token_with_proviers(
    user,
    project,
    drone=True,
    circle=True,
    travis=True,
    azure=True,
    clobber=True,
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
                feedstock_token, err_msg = read_feedstock_token(user, project)
                if err_msg:
                    failed = True
                    raise RuntimeError(err_msg)

                if circle:
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
                    try:
                        add_feedstock_token_to_drone(
                            user, project, feedstock_token, clobber
                        )
                    except Exception as e:
                        if "DEBUG_FEEDSTOCK_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                "Failed to register feedstock token for %s/%s"
                                " on drone!"
                            ) % (user, project)
                            failed = True
                            raise RuntimeError(err_msg)

                if travis:
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


def add_feedstock_token_to_drone(user, project, feedstock_token, clobber):
    from .ci_register import drone_session

    session = drone_session()

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
                travis_endpoint, repo_id=repo_id, ev_id=ev_id,
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
            allow_override=False, is_secret=True, value=feedstock_token,
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
