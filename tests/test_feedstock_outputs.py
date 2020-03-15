import os
import json
from unittest import mock

import pytest

from conda_smithy.feedstock_outputs import is_valid_feedstock_output


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
