#!/usr/bin/env python
import os

import requests

from conda_smithy import github
from conda_smithy.utils import (
    file_permissions,
)

try:
    anaconda_token = os.environ["BINSTAR_TOKEN"]
except KeyError:
    try:
        anaconda_token_path = os.path.expanduser("~/.conda-smithy/anaconda.token")
        if file_permissions(anaconda_token_path) != "0o600":
            raise ValueError("Incorrect permissions")
        with open(anaconda_token_path) as fh:
            anaconda_token = fh.read().strip()
        if not anaconda_token:
            raise ValueError()
    except (OSError, ValueError):
        print(
            "No anaconda token. Create a token via\n"
            '  anaconda auth --create --name conda-smithy --scopes "repos conda api"\n'
            "and put it in ~/.conda-smithy/anaconda.token with chmod 600"
        )


class LiveServerSession(requests.Session):
    """Utility class to avoid typing out urls all the time"""

    def __init__(self, prefix_url: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix_url = prefix_url

    def request(self, method, url: str, *args, **kwargs):
        from urllib.parse import urljoin

        url = urljoin(self.prefix_url, url)
        return super().request(method, url, *args, **kwargs)


def add_project_to_azure(user, project):
    from conda_smithy import azure_ci_utils

    if azure_ci_utils.repo_registered(user, project):
        print(f" * {user}/{project} already enabled on azure pipelines")
    else:
        azure_ci_utils.register_repo(user, project)
        print(f" * {user}/{project} has been enabled on azure pipelines")


def enable_namespace_app(org: str, project: str) -> None:
    app = 122481775 if org == "conda-forge" else "namespace-managed-runners"
    github.configure_github_app(org, project, app)


def disable_namespace_app(org: str, project: str) -> None:
    app = 122481775 if org == "conda-forge" else "namespace-managed-runners"
    github.configure_github_app(org, project, app, remove=True)


def enable_blacksmith_app(org: str, project: str) -> None:
    app = 122473844 if org == "conda-forge" else "blacksmith-sh"
    github.configure_github_app(org, project, app)


def disable_blacksmith_app(org: str, project: str) -> None:
    app = 122473844 if org == "conda-forge" else "blacksmith-sh"
    github.configure_github_app(org, project, app, remove=True)


def enable_depot_app(org: str, project: str) -> None:
    app = 137205076 if org == "conda-forge" else "depot-managed-runners"
    github.configure_github_app(org, project, app)


def disable_depot_app(org: str, project: str) -> None:
    app = 137205076 if org == "conda-forge" else "depot-managed-runners"
    github.configure_github_app(org, project, app, remove=True)


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
            f"Unable to register {user}/{repo} for conda-linting at this time as only "
            "conda-forge repos are supported."
        )

    headers = {"Authorization": f"token {github.gh_token()}"}
    url = f"https://api.github.com/repos/{user}/{repo}/hooks"

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


def _get_anaconda_token():
    try:
        return anaconda_token
    except NameError:
        raise RuntimeError(
            "You must have the anaconda token defined to do CI registration"
            "This requirement can be overriden by specifying `--without-anaconda-token`"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("user")
    parser.add_argument("project")
    args = parser.parse_args()

    add_conda_forge_webservice_hooks(args.user, args.project)
    print("Done")
