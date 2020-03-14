import os
from unittest import mock

import pytest

from conda_smithy.feedstock_tokens import (
    generate_and_write_feedstock_token,
    read_feedstock_token,
    feedstock_token_exists,
)


def test_generate_and_write_feedstock_token():
    user = 'bar'
    repo = 'foo'

    pth = os.path.expanduser("~/.conda-smithy/bar_foo_feedstock.token")

    try:
        generate_and_write_feedstock_token(user, repo)

        assert os.path.exists(pth)

        # we cannot do it twice
        with pytest.raises(RuntimeError):
            generate_and_write_feedstock_token(user, repo)
    finally:
        if os.path.exists(pth):
            os.remove(pth)


def test_read_feedstock_token():
    user = 'bar'
    repo = 'foo'
    pth = os.path.expanduser("~/.conda-smithy/bar_foo_feedstock.token")

    # no token
    token, err = read_feedstock_token(user, repo)
    assert "No token found in" in err
    assert token is None

    # empty
    try:
        os.system("touch " + pth)
        token, err = read_feedstock_token(user, repo)
        assert "Empty token found in" in err
        assert token is None
    finally:
        if os.path.exists(pth):
            os.remove(pth)

    # token ok
    try:
        generate_and_write_feedstock_token(user, repo)
        token, err = read_feedstock_token(user, repo)
        assert err is None
        assert token is not None

    finally:
        if os.path.exists(pth):
            os.remove(pth)


@pytest.mark.parametrize("retval", [
    True,
    False,
])
@pytest.mark.parametrize("project", [
    "bar",
    "bar-feedstock",
])
@pytest.mark.parametrize("repo", [
    "GITHUB_TOKEN",
    "${GITHUB_TOKEN}",
    "GH_TOKEN",
    "${GH_TOKEN}",
])
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_token_exists(gh_mock, git_mock, tmp_mock, tmpdir, repo, project, retval):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(tmpdir)

    user = "foo"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    if retval:
        with open(os.path.join(tmpdir, "tokens", "bar.json"), "w") as fp:
            fp.write("blarg")

    assert feedstock_token_exists(user, project, repo) is retval

    assert git_mock.Repo.clone_from.called_with(
        "abc123",
        str(tmpdir),
        depth=1,
    )


@pytest.mark.parametrize("project", [
    "bar",
    "bar-feedstock",
])
@pytest.mark.parametrize("repo", [
    "GITHUB_TOKEN",
    "${GITHUB_TOKEN}",
    "GH_TOKEN",
    "${GH_TOKEN}",
])
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_token_raises(gh_mock, git_mock, tmp_mock, tmpdir, repo, project):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(tmpdir)

    git_mock.Repo.clone_from.side_effect = ValueError("blarg")
    user = "foo"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    with open(os.path.join(tmpdir, "tokens", "bar.json"), "w") as fp:
        fp.write("blarg")

    with pytest.raises(RuntimeError) as e:
        feedstock_token_exists(user, project, repo)

    assert "Testing for the feedstock token for" in str(e.value)

    assert git_mock.Repo.clone_from.called_with(
        "abc123",
        str(tmpdir),
        depth=1,
    )
