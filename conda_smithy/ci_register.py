#!/usr/bin/env python
import os
import requests
import time
import sys

from . import github
from .utils import update_conda_forge_config


# https://circleci.com/docs/api#add-environment-variable

# curl -X POST --header "Content-Type: application/json" -d '{"name":"foo", "value":"bar"}'
# https://circleci.com/api/v1/project/:username/:project/envvar?circle-token=:token

try:
    with open(os.path.expanduser("~/.conda-smithy/circle.token"), "r") as fh:
        circle_token = fh.read().strip()
    if not circle_token:
        raise ValueError()
except (IOError, ValueError):
    print(
        "No circle token.  Create a token at https://circleci.com/account/api and\n"
        "put it in ~/.conda-smithy/circle.token"
    )

try:
    with open(os.path.expanduser("~/.conda-smithy/appveyor.token"), "r") as fh:
        appveyor_token = fh.read().strip()
    if not appveyor_token:
        raise ValueError()
except (IOError, ValueError):
    print(
        "No appveyor token. Create a token at https://ci.appveyor.com/api-token and\n"
        "Put one in ~/.conda-smithy/appveyor.token"
    )

try:
    with open(os.path.expanduser("~/.conda-smithy/drone.token"), "r") as fh:
        drone_token = fh.read().strip()
    if not drone_token:
        raise ValueError()
except (IOError, ValueError):
    print(
        "No drone token. Create a token at https://cloud.drone.io/account and\n"
        "Put one in ~/.conda-smithy/drone.token"
    )

try:
    anaconda_token = os.environ["BINSTAR_TOKEN"]
except KeyError:
    try:
        with open(
            os.path.expanduser("~/.conda-smithy/anaconda.token"), "r"
        ) as fh:
            anaconda_token = fh.read().strip()
        if not anaconda_token:
            raise ValueError()
    except (IOError, ValueError):
        print(
            "No anaconda token. Create a token via\n"
            '  anaconda auth --create --name conda-smithy --scopes "repos conda api"\n'
            "and put it in ~/.conda-smithy/anaconda.token"
        )

travis_endpoint = "https://api.travis-ci.com"
drone_endpoint = "https://cloud.drone.io"


class LiveServerSession(requests.Session):
    """Utility class to avoid typing out urls all the time"""

    def __init__(self, prefix_url=None, *args, **kwargs):
        super(LiveServerSession, self).__init__(*args, **kwargs)
        self.prefix_url = prefix_url

    def request(self, method, url, *args, **kwargs):
        from urllib.parse import urljoin

        url = urljoin(self.prefix_url, url)
        return super(LiveServerSession, self).request(
            method, url, *args, **kwargs
        )


def travis_headers():
    headers = {
        # If the user-agent isn't defined correctly, we will recieve a 403.
        "User-Agent": "Travis/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Travis-API-Version": "3",
    }
    travis_token = os.path.expanduser("~/.conda-smithy/travis.token")
    try:
        with open(travis_token, "r") as fh:
            token = fh.read().strip()
        if not token:
            raise ValueError
    except (IOError, ValueError):
        # We generally want the V3 API, but can currently only auth with V2:
        # https://github.com/travis-ci/travis-ci/issues/9273#issuecomment-370474214
        v2_headers = headers.copy()
        v2_headers["Accept"] = "application/vnd.travis-ci.2+json"
        del v2_headers["Travis-API-Version"]

        url = "{}/auth/github".format(travis_endpoint)
        data = {"github_token": github.gh_token()}
        response = requests.post(url, json=data, headers=v2_headers)
        if response.status_code != 201:
            response.raise_for_status()
        token = response.json()["access_token"]
        with open(travis_token, "w") as fh:
            fh.write(token)
        # TODO: Set the permissions on the file.

    headers["Authorization"] = "token {}".format(token)
    return headers


def add_token_to_circle(user, project):
    url_template = (
        "https://circleci.com/api/v1.1/project/github/{user}/{project}/envvar?"
        "circle-token={token}"
    )
    url = url_template.format(token=circle_token, user=user, project=project)
    data = {"name": "BINSTAR_TOKEN", "value": anaconda_token}
    response = requests.post(url, data)
    if response.status_code != 201:
        raise ValueError(response)


def drone_session():
    s = LiveServerSession(prefix_url=drone_endpoint)
    s.headers.update({"Authorization": f"Bearer {drone_token}"})
    return s


def add_token_to_drone(user, project):
    session = drone_session()
    response = session.post(
        f"/api/repos/{user}/{project}/secrets",
        json={
            "name": "BINSTAR_TOKEN",
            "data": anaconda_token,
            "pull_request": False,
        },
    )
    if response.status_code != 200:
        # Check that the token is in secrets already
        session = drone_session()
        response2 = session.get(f"/api/repos/{user}/{project}/secrets")
        response2.raise_for_status()
        for secret in response2.json():
            if "BINSTAR_TOKEN" == secret["name"]:
                return
    response.raise_for_status()


def drone_sync():
    session = drone_session()
    response = session.post("/api/user/repos?async=true")
    response.raise_for_status()


def add_project_to_drone(user, project):
    session = drone_session()
    response = session.post(f"/api/repos/{user}/{project}")
    if response.status_code != 200:
        # Check that the project is registered already
        session = drone_session()
        response = session.get(f"/api/repos/{user}/{project}")
        response.raise_for_status()


def regenerate_drone_webhooks(user, project):
    session = drone_session()
    response = session.post(f"/api/repos/{user}/{project}/repair")
    response.raise_for_status()


def add_project_to_circle(user, project):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url_template = (
        "https://circleci.com/api/v1.1/project/github/{component}?"
        "circle-token={token}"
    )

    # Note, we used to check to see whether the project was already registered, but it started
    # timing out once we had too many repos, so now the approach is simply "add it always".

    url = url_template.format(
        component="{}/{}/follow".format(user, project).lower(),
        token=circle_token,
    )
    response = requests.post(url, headers={})
    # It is a strange response code, but is doing what was asked...
    if response.status_code != 400:
        response.raise_for_status()

    # Note, here we are using a non-public part of the API and may change
    # Enable building PRs from forks
    url = url_template.format(
        component="{}/{}/settings".format(user, project).lower(),
        token=circle_token,
    )
    # Disable CircleCI secrets in builds of forked PRs explicitly.
    response = requests.put(
        url,
        headers=headers,
        json={"feature_flags": {"forks-receive-secret-env-vars": False}},
    )
    if response.status_code != 200:
        response.raise_for_status()
    # Enable CircleCI builds on forked PRs.
    response = requests.put(
        url, headers=headers, json={"feature_flags": {"build-fork-prs": True}}
    )
    if response.status_code != 200:
        response.raise_for_status()

    print(" * {}/{} enabled on CircleCI".format(user, project))


def add_project_to_azure(user, project):
    from . import azure_ci_utils

    if azure_ci_utils.repo_registered(user, project):
        print(
            " * {}/{} already enabled on azure pipelines".format(user, project)
        )
    else:
        azure_ci_utils.register_repo(user, project)
        print(
            " * {}/{} has been enabled on azure pipelines".format(
                user, project
            )
        )


def add_project_to_appveyor(user, project):
    headers = {"Authorization": "Bearer {}".format(appveyor_token)}
    url = "https://ci.appveyor.com/api/projects"

    response = requests.get(url, headers=headers)
    if response.status_code != 201:
        response.raise_for_status()
    repos = [repo["repositoryName"].lower() for repo in response.json()]

    if "{}/{}".format(user, project).lower() in repos:
        print(" * {}/{} already enabled on appveyor".format(user, project))
    else:
        data = {
            "repositoryProvider": "gitHub",
            "repositoryName": "{}/{}".format(user, project),
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code != 201:
            response.raise_for_status()
        print(" * {}/{} has been enabled on appveyor".format(user, project))


def appveyor_encrypt_binstar_token(feedstock_directory, user, project):
    headers = {"Authorization": "Bearer {}".format(appveyor_token)}
    url = "https://ci.appveyor.com/api/account/encrypt"
    response = requests.post(
        url, headers=headers, data={"plainValue": anaconda_token}
    )
    if response.status_code != 200:
        raise ValueError(response)

    with update_conda_forge_config(feedstock_directory) as code:
        code.setdefault("appveyor", {}).setdefault("secure", {})[
            "BINSTAR_TOKEN"
        ] = response.content.decode("utf-8")


def appveyor_configure(user, project):
    """Configure appveyor so that it skips building if there is no appveyor.yml present."""
    headers = {"Authorization": "Bearer {}".format(appveyor_token)}
    # I have reasons to believe this is all AppVeyor is doing to the API URL.
    if project.startswith("_"):
        project = project[1:]
    project = project.replace("_", "-").replace(".", "-")
    url = "https://ci.appveyor.com/api/projects/{}/{}/settings".format(
        user, project
    )
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise ValueError(response)
    content = response.json()
    settings = content["settings"]
    for required_setting in (
        "skipBranchesWithoutAppveyorYml",
        "rollingBuildsOnlyForPullRequests",
        "rollingBuilds",
    ):
        if not settings[required_setting]:
            print(
                "{: <30}: Current setting for {} = {}."
                "".format(
                    project, required_setting, settings[required_setting]
                )
            )
        settings[required_setting] = True

    url = "https://ci.appveyor.com/api/projects"
    response = requests.put(url, headers=headers, json=settings)
    if response.status_code != 204:
        raise ValueError(response)


def travis_wait_until_synced(ignore=False):
    headers = travis_headers()
    is_sync_url = "{}/user".format(travis_endpoint)
    for _ in range(20):
        response = requests.get(is_sync_url, headers=headers)
        content = response.json()
        print(".", end="")
        sys.stdout.flush()
        if "is_syncing" in content and content["is_syncing"] == False:
            break
        time.sleep(6)
    else:
        if ignore:
            print(" * Travis is being synced by somebody else. Ignoring")
        else:
            raise RuntimeError("Syncing has not finished for two minutes now.")
    print("")
    return content


def travis_repo_writable(repo_info):
    if "@permissions" not in repo_info:
        return False
    permissions = repo_info["@permissions"]
    if "admin" not in permissions or not permissions["admin"]:
        return False
    return True


def travis_get_repo_info(user, project, show_error=False):
    headers = travis_headers()
    url = "{}/repo/{user}%2F{project}".format(
        travis_endpoint, user=user, project=project
    )
    response = requests.get(url, headers=headers)
    try:
        response.raise_for_status()
        content = response.json()
        return content
    except requests.HTTPError as e:
        if show_error:
            print(e)
    return {}


def add_project_to_travis(user, project):
    # Make sure the travis-ci user has accepted all invitations
    if os.getenv("GH_TRAVIS_TOKEN"):
        gh = github.Github(os.getenv("GH_TRAVIS_TOKEN"))
        github.accept_all_repository_invitations(gh)

    headers = travis_headers()

    repo_info = travis_get_repo_info(user, project, show_error=False)
    if not travis_repo_writable(repo_info):
        # Travis needs syncing. Wait until other syncs are finished.
        print(" * Travis: checking if there's a syncing already", end="")
        sys.stdout.flush()
        user_info = travis_wait_until_synced(ignore=True)
        repo_info = travis_get_repo_info(user, project, show_error=False)
        if not travis_repo_writable(repo_info):
            if not repo_info:
                print(
                    " * Travis doesn't know about the repo, syncing (takes a few seconds).",
                    end="",
                )
            else:
                print(
                    " * Travis repo settings are not writable, syncing (takes a few seconds).",
                    end="",
                )
            sys.stdout.flush()
            sync_url = "{}/user/{}/sync".format(
                travis_endpoint, user_info["id"]
            )
            response = requests.post(sync_url, headers=headers)
            if response.status_code != 409:
                # 409 status code is for indicating that another synching might be happening at the
                # same time. This can happen in conda-forge/staged-recipes when two master builds
                # start at the same time
                response.raise_for_status()
            travis_wait_until_synced(ignore=False)
            repo_info = travis_get_repo_info(user, project)

    if not repo_info:
        msg = (
            "Unable to register the repo on Travis\n"
            '(Is it down? Is the "{}/{}" name spelt correctly? [note: case sensitive])'
        )
        raise RuntimeError(msg.format(user, project))

    if not travis_repo_writable(repo_info):
        msg = "Access denied for the repo {}/{}"
        raise RuntimeError(msg.format(user, project))

    if repo_info["active"] is True:
        print(" * {}/{} already enabled on travis-ci".format(user, project))
    else:
        repo_id = repo_info["id"]
        url = "{}/repo/{}/activate".format(travis_endpoint, repo_id)
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        print(" * {}/{} registered on travis-ci".format(user, project))


def travis_token_update_conda_forge_config(feedstock_directory, user, project):
    item = 'BINSTAR_TOKEN="{}"'.format(anaconda_token)
    slug = "{}%2F{}".format(user, project)

    with update_conda_forge_config(feedstock_directory) as code:
        code.setdefault("travis", {}).setdefault("secure", {})[
            "BINSTAR_TOKEN"
        ] = travis_encrypt_binstar_token(slug, item)


def travis_encrypt_binstar_token(repo, string_to_encrypt):
    # Copyright 2014 Matt Martz <matt@sivel.net>
    # All Rights Reserved.
    #
    #    Licensed under the Apache License, Version 2.0 (the "License"); you may
    #    not use this file except in compliance with the License. You may obtain
    #    a copy of the License at
    #
    #         https://www.apache.org/licenses/LICENSE-2.0
    #
    #    Unless required by applicable law or agreed to in writing, software
    #    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
    #    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
    #    License for the specific language governing permissions and limitations
    #    under the License.
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
    import base64

    keyurl = "https://api.travis-ci.com/repo/{0}/key_pair/generated".format(
        repo
    )
    r = requests.get(keyurl, headers=travis_headers())
    r.raise_for_status()
    public_key = r.json()["public_key"]
    key = RSA.importKey(public_key)
    cipher = PKCS1_v1_5.new(key)
    return base64.b64encode(cipher.encrypt(string_to_encrypt.encode())).decode(
        "utf-8"
    )


def travis_configure(user, project):
    """Configure travis so that it skips building if there is no .travis.yml present."""
    headers = travis_headers()

    repo_info = travis_get_repo_info(user, project)
    repo_id = repo_info["id"]

    if repo_info["active"] is not True:
        raise ValueError(
            "Repo {user}/{project} is not active on Travis CI".format(
                user=user, project=project
            )
        )

    settings = [
        ("builds_only_with_travis_yml", True),
        ("auto_cancel_pull_requests", True),
    ]
    for name, value in settings:
        url = "{}/repo/{repo_id}/setting/{name}".format(
            travis_endpoint, repo_id=repo_id, name=name
        )
        data = {"setting.value": value}
        response = requests.patch(url, json=data, headers=headers)
        if response.status_code != 204:
            response.raise_for_status()


def add_token_to_travis(user, project):
    """Add the BINSTAR_TOKEN to travis."""

    headers = travis_headers()

    repo_info = travis_get_repo_info(user, project)
    repo_id = repo_info["id"]

    r = requests.get(
        "{}/repo/{repo_id}/env_vars".format(travis_endpoint, repo_id=repo_id),
        headers=headers,
    )
    if r.status_code != 200:
        r.raise_for_status()

    have_token = False
    ev_id = None
    for ev in r.json()["env_vars"]:
        if ev["name"] == "BINSTAR_TOKEN":
            have_token = True
            ev_id = ev["id"]

    data = {
        "env_var.name": "BINSTAR_TOKEN",
        "env_var.value": anaconda_token,
        "env_var.public": "false",
    }

    if have_token:
        r = requests.patch(
            "{}/repo/{repo_id}/env_var/{ev_id}".format(
                travis_endpoint, repo_id=repo_id, ev_id=ev_id,
            ),
            headers=headers,
            json=data,
        )
        r.raise_for_status()
    else:
        r = requests.post(
            "{}/repo/{repo_id}/env_vars".format(
                travis_endpoint, repo_id=repo_id
            ),
            headers=headers,
            json=data,
        )
        if r.status_code != 201:
            r.raise_for_status()


def travis_cleanup(org, project):
    if os.getenv("GH_TRAVIS_TOKEN"):
        gh = github.Github(os.getenv("GH_TRAVIS_TOKEN"))
        github.remove_from_project(gh, org, project)


def get_conda_hook_info(hook_url, events):
    payload = {
        "name": "web",
        "active": True,
        "events": events,
        "config": {"url": hook_url, "content_type": "json"},
    }

    return hook_url, payload


def add_conda_forge_webservice_hooks(user, repo):
    if user != "conda-forge":
        print(
            "Unable to register {}/{} for conda-linting at this time as only "
            "conda-forge repos are supported.".format(user, repo)
        )

    headers = {"Authorization": "token {}".format(github.gh_token())}
    url = "https://api.github.com/repos/{}/{}/hooks".format(user, repo)

    # Get the current hooks to determine if anything needs doing.
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    registered = response.json()
    hook_by_url = {
        hook["config"].get("url"): hook
        for hook in registered
        if "url" in hook["config"]
    }

    hooks = [
        get_conda_hook_info(
            "https://conda-forge.herokuapp.com/conda-linting/hook",
            ["pull_request"],
        ),
        get_conda_hook_info(
            "https://conda-forge.herokuapp.com/conda-forge-feedstocks/hook",
            ["push", "repository"],
        ),
        get_conda_hook_info(
            "https://conda-forge.herokuapp.com/conda-forge-teams/hook",
            ["push", "repository"],
        ),
        get_conda_hook_info(
            "https://conda-forge.herokuapp.com/conda-forge-command/hook",
            [
                "pull_request_review",
                "pull_request",
                "pull_request_review_comment",
                "issue_comment",
                "issues",
            ],
        ),
    ]

    for hook in hooks:
        hook_url, payload = hook
        if hook_url not in hook_by_url:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                response.raise_for_status()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("user")
    parser.add_argument("project")
    args = parser.parse_args()

    #    add_project_to_circle(args.user, args.project)
    #    add_project_to_appveyor(args.user, args.project)
    #    add_project_to_travis(args.user, args.project)
    #    appveyor_encrypt_binstar_token('../udunits-delme-feedstock', args.user, args.project)
    #    appveyor_configure('conda-forge', 'glpk-feedstock')
    #    travis_token_update_conda_forge_config('../udunits-delme-feedstock', args.user, args.project)
    add_conda_forge_webservice_hooks(args.user, args.project)
    print("Done")
