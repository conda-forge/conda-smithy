import os
import json
from unittest import mock
from collections import OrderedDict

import pytest

from binstar_client import BinstarError

from conda_smithy.feedstock_outputs import (
    is_valid_feedstock_output,
    is_valid_output_hash,
    copy_feedstock_outputs,
    validate_feedstock_outputs,
)


@mock.patch("conda_smithy.feedstock_outputs._get_ac_api")
def test_copy_feedstock_outputs(ac):
    ac.return_value.copy.side_effect = [True, BinstarError("blah")]

    outputs = OrderedDict()
    outputs["boo"] = {"version": "1", "name": "boohoo"}
    outputs["blah"] = {"version": "2", "name": "blahha"}

    copied = copy_feedstock_outputs(outputs, "staging", "prod")

    assert copied == {"boo": True, "blah": False}

    assert ac.return_value.copy.called_with(
        "staging",
        "boohoo",
        "1",
        basename="boo",
        to_owner="prod",
        from_label="main",
        to_label="main",
    )

    assert ac.return_value.copy.called_with(
        "staging",
        "blahha",
        "2",
        basename="blah",
        to_owner="prod",
        from_label="main",
        to_label="main",
    )


@mock.patch("conda_smithy.feedstock_outputs.is_valid_output_hash")
@mock.patch("conda_smithy.feedstock_outputs.is_valid_feedstock_output")
@mock.patch("conda_smithy.feedstock_outputs.is_valid_feedstock_token")
def test_validate_feedstock_outputs_badtoken(
    valid_token, valid_out, valid_hash
):
    valid_token.return_value = False
    valid, errs = validate_feedstock_outputs(
        "foo",
        "bar-feedstock",
        {"a": {}, "b": {}},
        "abc",
        "staging",
        "output_repo",
        "token_repo",
        register=True,
    )

    assert not any(v for v in valid.values())
    assert ["invalid feedstock token"] == errs

    valid_out.assert_not_called()
    valid_hash.assert_not_called()


@mock.patch("conda_smithy.feedstock_outputs.is_valid_output_hash")
@mock.patch("conda_smithy.feedstock_outputs.is_valid_feedstock_output")
@mock.patch("conda_smithy.feedstock_outputs.is_valid_feedstock_token")
def test_validate_feedstock_outputs_badoutputhash(
    valid_token, valid_out, valid_hash
):
    valid_token.return_value = True
    valid_out.return_value = {
        "a-name": True,
        "b-name": False,
        "c-name": True,
        "d-name": False,
    }
    valid_hash.return_value = {
        "a": False,
        "b": True,
        "c": True,
        "d": False,
    }
    valid, errs = validate_feedstock_outputs(
        "foo",
        "bar-feedstock",
        {
            "a": {"name": "a-name"},
            "b": {"name": "b-name"},
            "c": {"name": "c-name"},
            "d": {"name": "d-name"},
        },
        "abc",
        "staging",
        "output_repo",
        "token_repo",
        register=True,
    )

    assert valid == {
        "a": False,
        "b": False,
        "c": True,
        "d": False,
    }
    assert len(errs) == 4
    assert "output b not allowed for foo/bar-feedstock" in errs
    assert "output d not allowed for foo/bar-feedstock" in errs
    assert "output a does not have a valid md5 checksum" in errs
    assert "output d does not have a valid md5 checksum" in errs


def test_is_valid_output_hash():
    outputs = {
        "linux-64/python-3.8.2-h9d8adfe_4_cpython.tar.bz2": {
            "name": "python",
            "version": "3.8.2",
            "md5": "7382171fb4c13dbedf98e0bd9b60f165",
        },
        # bad hash
        "osx-64/python-3.8.2-hdc38147_4_cpython.tar.bz2": {
            "name": "python",
            "version": "3.8.2",
            "md5": "7382171fb4c13dbedf98e0bd9b60f165",
        },
        # not a package
        "linux-64/python-3.8.2-h9d8adfe_4_cpython.tar": {
            "name": "python",
            "version": "3.8.2",
            "md5": "7382171fb4c13dbedf98e0bd9b60f165",
        },
        # bad metadata
        "linux-64/python-3.7.6-h357f687_4_cpython.tar.bz2": {
            "name": "dskljfals",
            "version": "3.4.5",
            "md5": "2f347da4a40715a5228412e56fb035d8",
        },
    }

    valid = is_valid_output_hash("conda-forge", outputs)
    assert valid == {
        "linux-64/python-3.8.2-h9d8adfe_4_cpython.tar.bz2": True,
        # bad hash
        "osx-64/python-3.8.2-hdc38147_4_cpython.tar.bz2": False,
        # not a package
        "linux-64/python-3.8.2-h9d8adfe_4_cpython.tar": False,
        # bad metadata
        "linux-64/python-3.7.6-h357f687_4_cpython.tar.bz2": False,
    }


@pytest.mark.parametrize("register", [True, False])
@pytest.mark.parametrize(
    "project", ["foo", "foo-feedstock", "blah", "blarg", "boo"]
)
@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_outputs.tempfile")
@mock.patch("conda_smithy.feedstock_outputs.git")
@mock.patch("conda_smithy.github.gh_token")
def test_is_valid_feedstock_output(
    gh_mock, git_mock, tmp_mock, tmpdir, repo, project, register
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )

    os.makedirs(os.path.join(tmpdir, "outputs"), exist_ok=True)
    with open(os.path.join(tmpdir, "outputs", "bar.json"), "w") as fp:
        json.dump({"feedstocks": ["foo", "blah"]}, fp)

    with open(os.path.join(tmpdir, "outputs", "goo.json"), "w") as fp:
        json.dump({"feedstocks": ["blarg"]}, fp)

    user = "conda-forge"

    outputs = ["bar", "goo", "glob"]

    valid = is_valid_feedstock_output(
        user, project, outputs, repo, register=register
    )

    repo = git_mock.Repo.clone_from.return_value

    assert git_mock.Repo.clone_from.called_with(
        "abc123", str(tmpdir), depth=1,
    )

    if project in ["foo", "foo-feedstock"]:
        assert valid == {"bar": True, "goo": False, "glob": True}
    elif project == "blah":
        assert valid == {"bar": True, "goo": False, "glob": True}
    elif project == "blarg":
        assert valid == {"bar": False, "goo": True, "glob": True}
    elif project == "boo":
        assert valid == {"bar": False, "goo": False, "glob": True}

    if register:
        assert os.path.exists(os.path.join(tmpdir, "outputs", "glob.json"))
        with open(os.path.join(tmpdir, "outputs", "glob.json"), "r") as fp:
            data = json.load(fp)
        assert data == {"feedstocks": [project.replace("-feedstock", "")]}

        assert repo.index.add.called_with(
            os.path.join(tmpdir, "outputs", "glob.json")
        )
        assert repo.index.commit.called_with(
            "added output %s %s/%s"
            % ("glob", user, project.replace("-feedstock", ""))
        )
        assert repo.remote.return_value.pull.called_with(rebase=True)
        assert repo.remote.return_value.push.called_with()
    else:
        repo.remote.return_value.pull.assert_not_called()
        repo.remote.return_value.push.assert_not_called()
        repo.index.commit.assert_not_called()
        repo.index.add.assert_not_called()
        assert not os.path.exists(os.path.join(tmpdir, "outputs", "glob.json"))
