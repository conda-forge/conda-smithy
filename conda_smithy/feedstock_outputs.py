"""
This module registers and validates feedstock outputs.
"""
import tempfile
import os
import json
import hmac
import urllib.parse

import requests

import git

from .feedstock_tokens import is_valid_feedstock_token


def validate_feedstock_outputs(
    user, project, outputs, feedstock_token, conda_channel, output_repo, token_repo, register=True
):
    valid = {o: False for o in outputs}

    if not is_valid_feedstock_token(user, project, feedstock_token, token_repo):
        return valid, ["invalid feedstock token"]

    valid_outputs = is_valid_feedstock_output(
        user, project, [o["name"] for _, o in outputs.items()], output_repo, register=register)

    valid_hashes = is_valid_output_hash(conda_channel, outputs)

    errors = []
    for o in outputs:
        _errors = []
        if not valid_outputs[outputs[o]["name"]]:
            _errors.append("output %s not allowed for %s/%s" % (o, user, project))
        if not valid_hashes[o]:
            _errors.append("output %s does not have a valid md5 checksum" % o)

        if len(_errors) > 0:
            errors.extend(_errors)
        else:
            valid[o] = True

    return valid, errors


def is_valid_output_hash(conda_channel, outputs):
    """Test if a set of outputs have valid hashes.

    Parameters
    ----------
    conda_channel : str
        The conda channel to validate against.
    outputs : dict
        A dictionary mapping each full qualified output in the conda index
        to a hash ("md5"), its name ("name"), and version ("version").

    Returns
    -------
    valid : dict
        A dict keyed on output name with True if it is valid and False
        otherwise.
    """

    valid = {o: False for o in outputs}

    for out_name, out in outputs.items():
        url = (
            "https://api.anaconda.org/dist/{conda_channel}/"
            "{name}/{version}/{encoded_name}"
        ).format(
            conda_channel=conda_channel,
            name=out["name"],
            version=out["version"],
            encoded_name=urllib.parse.quote(out_name, safe=""),
        )
        r = requests.get(url, headers={"Accept": "application/json"})
        if r.status_code != 200:
            continue

        valid[out_name] = hmac.compare_digest(r.json()["md5"], out["md5"])

    return valid


def is_valid_feedstock_output(user, project, outputs, output_repo, register=True):
    """Test if feedstock outputs are valid. Optionally register them if they do not exist.

    Parameters
    ----------
    user : str
        The GitHub user or org.
    project : str
        The GitHub repo.
    outputs : list of str
        List of output names to validate.
    output_repo : str
        The repo with the output registry.
    register : bool
        If True, attempt to register any outputs that do not exist by pushing
        the proper json blob to `output_repo`. Default is True.

    Returns
    -------
    valid : dict
        A dict keyed on output name with True if it is valid and False
        otherwise.
    """
    from .github import gh_token
    github_token = gh_token()

    feedstock = project.replace("-feedstock", "")

    valid = {o: False for o in outputs}
    made_commit = False

    with tempfile.TemporaryDirectory() as tmpdir:
        _output_repo = (
            output_repo.replace("$GITHUB_TOKEN", github_token)
            .replace("${GITHUB_TOKEN}", github_token)
            .replace("$GH_TOKEN", github_token)
            .replace("${GH_TOKEN}", github_token)
        )
        repo = git.Repo.clone_from(_output_repo, tmpdir, depth=1)

        for o in outputs:
            pth = os.path.join(tmpdir, "outputs", o + ".json")

            if not os.path.exists(pth):
                # no output exists, so we can add it
                valid[o] = True

                if register:
                    with open(pth, "w") as fp:
                        json.dump({"feedstocks": [feedstock]}, fp)
                    repo.index.add(pth)
                    repo.index.commit("added output %s %s/%s" % (o, user, project))
                    made_commit = True
            else:
                # make sure feedstock is ok
                with open(pth, "r") as fp:
                    data = json.load(fp)
                valid[o] = feedstock in data["feedstocks"]

        if register and made_commit:
            repo.remote().pull(rebase=True)
            repo.remote().push()

    return valid
