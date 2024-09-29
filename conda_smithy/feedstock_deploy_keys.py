import os
import subprocess
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout

import github
import requests


class FeedstockDeployKeyError(Exception):
    """Custom exception for sanitized deploy key errors."""


@contextmanager
def _secure_io():
    """context manager that redirects stdout and
    stderr to /dev/null to avoid spilling tokens"""

    if "DEBUG_FEEDSTOCK_DEPLOY_KEYS" in os.environ:
        yield
    else:
        # the redirect business
        with open(os.devnull, "w") as fp:
            with redirect_stdout(fp), redirect_stderr(fp):
                yield


def _deploy_key_local_path(owner: str, repo: str) -> str:
    pth = os.path.join(
        "~",
        ".conda-smithy",
        f"{owner}_{repo}_id_ed25519",
    )
    return os.path.expanduser(pth)


def _gen_deploy_key(owner: str, repo: str) -> str:
    """Generate a deploy key for the feedstock.

    Returns the path to the private key file.

    You can get the public key by appending '.pub' to the path.
    """

    with _secure_io():
        try:
            key_path = _deploy_key_local_path(owner, repo)
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t",
                    "ed25519",
                    "-C",
                    f"git@github.com:{owner}/{repo}.git",
                    "-N",
                    "",
                    "-f",
                    key_path,
                ],
                check=True,
            )
        except Exception as e:
            if "DEBUG_FEEDSTOCK_DEPLOY_KEYS" in os.environ:
                raise e
            key_path = None

        return key_path


def _delete_deploy_key(owner: str, repo: str, key_id: str):
    # there is not method in pygithub for this call
    from conda_smithy.github import gh_token

    github_token = gh_token()

    requests.delete(
        f"https://api.github.com/repos/{owner}/{repo}/keys/{key_id}",
        headers={"Authorization": f"Bearer {github_token}"},
    ).raise_for_status()


def _remove_oldest_deploy_key(
    owner: str, repo: str, gh_repo: github.Repository.Repository
):
    """Remove the oldest deploy key from the feedstock repository."""
    key_mapping = {}
    for key in gh_repo.get_keys():
        ts = int(key.title.split("-")[-1])
        key_mapping[ts] = key.id
    if len(key_mapping) > 2:
        oldest_ts = sorted(key_mapping.keys())[0]
        _delete_deploy_key(owner, repo, str(key_mapping[oldest_ts]))


def _register_deploy_key(owner: str, repo: str, key_file: str) -> bool:
    """Register a deploy key with the feedstock repository."""

    with _secure_io():
        try:
            with open(key_file + ".pub") as f:
                public_key = f.read().strip()

            with open(key_file) as f:
                private_key = f.read().strip()

            # Get the github token
            from conda_smithy.github import gh_token

            github_token = gh_token()

            # Register the key
            gh = github.Github(auth=github.Auth.Token(github_token))
            gh_repo = gh.get_repo(f"{owner}/{repo}")
            gh_repo.create_key(
                f"conda-smithy-deploy-key-{str(int(time.time()))}",
                public_key,
                read_only=False,
            )
            # this call will update an existing secret if needed
            gh_repo.create_secret(
                "CONDA_SMITHY_DEPLOY_KEY",
                private_key,
            )

            # we remove the oldest key if there is more than two
            # this lets us rotate keys without existing jobs failing
            _remove_oldest_deploy_key(owner, repo, gh_repo)

            didit = True
        except Exception as e:
            if "DEBUG_FEEDSTOCK_DEPLOY_KEYS" in os.environ:
                raise e
            didit = False

    return didit


def set_feedstock_deploy_key(owner: str, repo: str) -> bool:
    """Generate and register a feedstock deplot key, rotating existing keys if needed.

    Parameters
    ----------
    owner : str
        The owner of the repository
    repo : str
        The repository name
    """
    try:
        key_file = _gen_deploy_key(owner, repo)

        if key_file is None:
            didit = False
        else:
            didit = _register_deploy_key(owner, repo, key_file)

        if not didit:
            raise FeedstockDeployKeyError(
                f"Failed to set a deploy key for {owner}/{repo}. Try the command "
                "locally with the DEBUG_FEEDSTOCK_DEPLOY_KEYS environment variable "
                "set to see the error."
            )
    finally:
        key_file = _deploy_key_local_path(owner, repo)
        for fname in [key_file, key_file + ".pub"]:
            try:
                os.remove(fname)
            except Exception:
                pass
