import os
import json
from unittest import mock

import pytest
import scrypt

from conda_smithy.feedstock_tokens import (
    generate_and_write_feedstock_token,
    read_feedstock_token,
    feedstock_token_exists,
    register_feedstock_token,
    register_feedstock_token_with_proviers,
)


def test_generate_and_write_feedstock_token():
    user = "bar"
    repo = "foo"

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
    user = "bar"
    repo = "foo"
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


@pytest.mark.parametrize("retval", [True, False])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_token_exists(
    gh_mock, git_mock, tmp_mock, tmpdir, repo, project, retval
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )

    user = "foo"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    if retval:
        with open(os.path.join(tmpdir, "tokens", "bar.json"), "w") as fp:
            fp.write("blarg")

    assert feedstock_token_exists(user, project, repo) is retval

    assert git_mock.Repo.clone_from.called_with(
        "abc123", str(tmpdir), depth=1,
    )


@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_token_raises(
    gh_mock, git_mock, tmp_mock, tmpdir, repo, project
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )

    git_mock.Repo.clone_from.side_effect = ValueError("blarg")
    user = "foo"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    with open(os.path.join(tmpdir, "tokens", "bar.json"), "w") as fp:
        fp.write("blarg")

    with pytest.raises(RuntimeError) as e:
        feedstock_token_exists(user, project, repo)

    assert "Testing for the feedstock token for" in str(e.value)

    assert git_mock.Repo.clone_from.called_with(
        "abc123", str(tmpdir), depth=1,
    )


@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.secrets")
@mock.patch("conda_smithy.feedstock_tokens.os.urandom")
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_register_feedstock_token_works(
    gh_mock, git_mock, tmp_mock, osuran_mock, secrets_mock, tmpdir, repo
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )
    secrets_mock.token_hex.return_value = "fgh"
    osuran_mock.return_value = b"\x80SA"

    user = "foo"
    project = "bar"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    pth = os.path.expanduser("~/.conda-smithy/foo_bar_feedstock.token")
    token_json_pth = os.path.join(tmpdir, "tokens", "bar.json")

    try:
        generate_and_write_feedstock_token(user, project)

        register_feedstock_token(user, project, repo)

    finally:
        if os.path.exists(pth):
            os.remove(pth)

    assert git_mock.Repo.clone_from.called_with(
        "abc123", str(tmpdir), depth=1,
    )

    repo = git_mock.Repo.clone_from.return_value
    assert repo.index.add.called_with(token_json_pth)
    assert repo.index.commit.called_with(
        "added token for %s/%s" % (user, project)
    )
    assert repo.remote.return_value.pull.called_with(rebase=True)
    assert repo.remote.return_value.push.called_with()

    salted_token = scrypt.hash("fgh", b"\x80SA", buflen=256)
    data = {
        "salt": b"\x80SA".hex(),
        "hashed_token": salted_token.hex(),
    }

    with open(token_json_pth, "r") as fp:
        assert json.load(fp) == data


@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.secrets")
@mock.patch("conda_smithy.feedstock_tokens.os.urandom")
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_register_feedstock_token_notoken(
    gh_mock, git_mock, tmp_mock, osuran_mock, secrets_mock, tmpdir, repo
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )
    secrets_mock.token_hex.return_value = "fgh"
    osuran_mock.return_value = b"\x80SA"

    user = "foo"
    project = "bar"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    pth = os.path.expanduser("~/.conda-smithy/foo_bar_feedstock.token")
    token_json_pth = os.path.join(tmpdir, "tokens", "bar.json")

    try:
        with pytest.raises(RuntimeError) as e:
            register_feedstock_token(user, project, repo)
    finally:
        if os.path.exists(pth):
            os.remove(pth)

    git_mock.Repo.clone_from.assert_not_called()

    repo = git_mock.Repo.clone_from.return_value
    repo.index.add.assert_not_called()
    repo.index.commit.assert_not_called()
    repo.remote.return_value.pull.assert_not_called()
    repo.remote.return_value.push.assert_not_called()

    assert not os.path.exists(token_json_pth)

    assert "No token found in" in str(e.value)


@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.secrets")
@mock.patch("conda_smithy.feedstock_tokens.os.urandom")
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_register_feedstock_token_exists_already(
    gh_mock, git_mock, tmp_mock, osuran_mock, secrets_mock, tmpdir, repo
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )
    secrets_mock.token_hex.return_value = "fgh"
    osuran_mock.return_value = b"\x80SA"

    user = "foo"
    project = "bar"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    pth = os.path.expanduser("~/.conda-smithy/foo_bar_feedstock.token")
    token_json_pth = os.path.join(tmpdir, "tokens", "bar.json")
    with open(token_json_pth, "w") as fp:
        fp.write("blarg")

    try:
        generate_and_write_feedstock_token(user, project)

        with pytest.raises(RuntimeError) as e:
            register_feedstock_token(user, project, repo)

    finally:
        if os.path.exists(pth):
            os.remove(pth)

    assert git_mock.Repo.clone_from.called_with(
        "abc123", str(tmpdir), depth=1,
    )

    repo = git_mock.Repo.clone_from.return_value
    repo.index.add.assert_not_called()
    repo.index.commit.assert_not_called()
    repo.remote.return_value.pull.assert_not_called()
    repo.remote.return_value.push.assert_not_called()

    assert "Token for repo foo/bar already exists!" in str(e.value)


@pytest.mark.parametrize("drone", [True, False])
@pytest.mark.parametrize("circle", [True, False])
@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("travis", [True, False])
@pytest.mark.parametrize("clobber", [True, False])
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
def test_register_feedstock_token_with_proviers(
    azure_mock,
    travis_mock,
    circle_mock,
    drone_mock,
    drone,
    circle,
    travis,
    azure,
    clobber,
):
    user = "foo"
    project = "bar"

    pth = os.path.expanduser("~/.conda-smithy/foo_bar_feedstock.token")

    try:
        generate_and_write_feedstock_token(user, project)
        feedstock_token, _ = read_feedstock_token(user, project)

        register_feedstock_token_with_proviers(
            user,
            project,
            drone=drone,
            circle=circle,
            travis=travis,
            azure=azure,
            clobber=clobber,
        )

        if drone:
            assert drone_mock.called_with(
                user, project, feedstock_token, clobber
            )
        else:
            drone_mock.assert_not_called()

        if circle:
            assert circle_mock.called_with(
                user, project, feedstock_token, clobber
            )
        else:
            circle_mock.assert_not_called()

        if travis:
            assert travis_mock.called_with(
                user, project, feedstock_token, clobber
            )
        else:
            travis_mock.assert_not_called()

        if azure:
            assert azure_mock.called_with(
                user, project, feedstock_token, clobber
            )
        else:
            azure_mock.assert_not_called()
    finally:
        if os.path.exists(pth):
            os.remove(pth)


@pytest.mark.parametrize("drone", [True, False])
@pytest.mark.parametrize("circle", [True, False])
@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("travis", [True, False])
@pytest.mark.parametrize("clobber", [True, False])
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
def test_register_feedstock_token_with_proviers_notoken(
    azure_mock,
    travis_mock,
    circle_mock,
    drone_mock,
    drone,
    circle,
    travis,
    azure,
    clobber,
):
    user = "foo"
    project = "bar"

    with pytest.raises(RuntimeError) as e:
        register_feedstock_token_with_proviers(
            user,
            project,
            drone=drone,
            circle=circle,
            travis=travis,
            azure=azure,
            clobber=clobber,
        )

    assert "No token" in str(e.value)

    drone_mock.assert_not_called()
    circle_mock.assert_not_called()
    travis_mock.assert_not_called()
    azure_mock.assert_not_called()


@pytest.mark.parametrize("provider", ["drone", "circle", "travis", "azure"])
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
def test_register_feedstock_token_with_proviers_error(
    azure_mock, travis_mock, circle_mock, drone_mock, provider,
):
    user = "foo"
    project = "bar"

    pth = os.path.expanduser("~/.conda-smithy/foo_bar_feedstock.token")

    if provider == "drone":
        drone_mock.side_effect = ValueError("blah")
    if provider == "circle":
        circle_mock.side_effect = ValueError("blah")
    if provider == "travis":
        travis_mock.side_effect = ValueError("blah")
    if provider == "azure":
        azure_mock.side_effect = ValueError("blah")

    try:
        generate_and_write_feedstock_token(user, project)
        feedstock_token, _ = read_feedstock_token(user, project)

        with pytest.raises(RuntimeError) as e:
            register_feedstock_token_with_proviers(
                user, project,
            )

        assert "on %s" % provider in str(e.value)
    finally:
        if os.path.exists(pth):
            os.remove(pth)
