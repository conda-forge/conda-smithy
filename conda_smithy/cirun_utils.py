import os
from functools import cache

from cirun import Cirun

# To get this id, got to https://github.com/organizations/<ORG-NAME>/settings/installations
# and then click on the Configure button next to Cirun Application, then copy
# the installation id from the URL, it would look something like:
# https://github.com/organizations/conda-forge/settings/installations/18453316
CIRUN_INSTALLATION_ID = os.environ.get("CIRUN_INSTALLATION_ID", 18453316)


def enable_cirun_for_project(owner, repo):
    """Enable the cirun.io Github Application for a particular repository."""
    print(f"Enabling cirun for {owner}/{repo} ...")
    cirun = _get_cirun_client()
    assert CIRUN_INSTALLATION_ID
    return cirun.set_repo(
        f"{owner}/{repo}", installation_id=CIRUN_INSTALLATION_ID
    )


def add_repo_to_cirun_resource(owner, repo, resource, cirun_policy_args):
    """Grant access to a cirun resource to a particular repository, with a particular policy."""
    cirun = _get_cirun_client()
    policy_args = {"pull_request": False}
    if cirun_policy_args:
        if "pull_request" in cirun_policy_args:
            policy_args["pull_request"] = True
    print(
        f"Adding repo {owner}/{repo} to resource {resource} with policy_args: {policy_args}"
    )
    response = cirun.add_repo_to_resources(
        owner,
        repo,
        resources=[resource],
        teams=[repo],
        policy_args=policy_args,
    )
    print(f"response: {response} | {response.json().keys()}")
    return response


def remove_repo_from_cirun_resource(owner, repo, resource):
    """Revoke access to a cirun resource to a particular repository, with a particular policy."""
    cirun = _get_cirun_client()
    print(f"Removing repo {owner}/{repo} from resource {resource}.")
    response = cirun.remove_repo_from_resources(owner, repo, [resource])
    print(f"response: {response} | {response.json().keys()}")
    return response


@cache
def _get_cirun_client():
    try:
        return Cirun()
    except KeyError:
        raise RuntimeError(
            "You must have CIRUN_API_KEY defined to do Cirun CI registration"
            "This requirement can be overriden by specifying `--without-cirun`"
        )
