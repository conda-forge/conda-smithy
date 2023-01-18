import os
import json
from unittest import mock
import base64

import pytest
import scrypt

from conda_smithy.feedstock_tokens import (
    feedstock_token_local_path,
    feedstock_token_repo_path,
    generate_and_write_feedstock_token,
    read_feedstock_token,
    feedstock_token_exists,
    register_feedstock_token,
    register_feedstock_token_with_proviers,
    is_valid_feedstock_token,
    FeedstockTokenError,
)

from conda_smithy.ci_register import drone_default_endpoint


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo",
    [
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens",
    ],
)
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_tokens_roundtrip(
    gh_mock,
    repo,
    project,
    requests_mock,
    ci,
):
    gh_mock.return_value = "abc123"

    user = "foo"
    pth = feedstock_token_local_path(user, project, ci=ci)
    reg_pth = feedstock_token_repo_path(project, ci=ci)
    try:
        generate_and_write_feedstock_token(user, project, ci=ci)
        assert os.path.exists(pth)
        with open(pth, "r") as fp:
            feedstock_token = fp.read().strip()

        requests_mock.get(
            "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
            % reg_pth,
            status_code=404,
        )
        requests_mock.put(
            "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
            % reg_pth,
            status_code=201,
        )

        register_feedstock_token(user, project, repo, ci=ci)
        assert requests_mock.call_count == 2
        assert (
            requests_mock.request_history[-1].headers["Authorization"]
            == "Bearer abc123"
        )
        assert (
            requests_mock.request_history[-2].headers["Authorization"]
            == "Bearer abc123"
        )

        data = {}
        data.update(requests_mock.request_history[-1].json())
        data["encoding"] = "base64"
        requests_mock.get(
            "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
            % reg_pth,
            status_code=200,
            json=data,
        )

        assert is_valid_feedstock_token(
            user, project, feedstock_token, repo, ci=ci
        )
        assert requests_mock.call_count == 3
        assert (
            requests_mock.request_history[-1].headers["Authorization"]
            == "Bearer abc123"
        )
    finally:
        if os.path.exists(pth):
            os.remove(pth)


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo",
    [
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens",
    ],
)
@mock.patch("conda_smithy.github.gh_token")
def test_is_valid_feedstock_token_nofile(
    gh_mock,
    repo,
    project,
    ci,
    requests_mock,
):
    gh_mock.return_value = "abc123"

    user = "foo"
    feedstock_token = "akdjhfl"
    reg_pth = feedstock_token_repo_path(project, ci=ci)
    requests_mock.get(
        "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
        % reg_pth,
        status_code=404,
    )
    retval = is_valid_feedstock_token(
        user, project, feedstock_token, repo, ci=ci
    )
    assert not retval
    assert requests_mock.call_count == 1
    assert (
        requests_mock.request_history[-1].headers["Authorization"]
        == "Bearer abc123"
    )


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo",
    [
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens",
    ],
)
@mock.patch("conda_smithy.github.gh_token")
def test_is_valid_feedstock_token_badtoken(
    gh_mock,
    repo,
    project,
    ci,
    requests_mock,
):
    gh_mock.return_value = "abc123"

    user = "foo"
    feedstock_token = "akdjhfl"
    reg_pth = feedstock_token_repo_path(project, ci=ci)
    requests_mock.get(
        "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
        % reg_pth,
        status_code=200,
        json={
            "encoding": "base64",
            "content": base64.standard_b64encode(
                json.dumps(
                    {"salt": b"adf".hex(), "hashed_token": b"fgh".hex()}
                ).encode("utf-8")
            ).decode("ascii"),
        },
    )

    retval = is_valid_feedstock_token(
        user, project, feedstock_token, repo, ci=ci
    )
    assert not retval
    assert requests_mock.call_count == 1
    assert (
        requests_mock.request_history[-1].headers["Authorization"]
        == "Bearer abc123"
    )


@pytest.mark.parametrize("ci", [None, "azure"])
def test_generate_and_write_feedstock_token(ci):
    user = "bar"
    repo = "foo"

    if ci:
        pth = os.path.expanduser("~/.conda-smithy/bar_%s_foo.token" % ci)
        opth = os.path.expanduser("~/.conda-smithy/bar_foo.token")
    else:
        pth = os.path.expanduser("~/.conda-smithy/bar_foo.token")
        opth = os.path.expanduser("~/.conda-smithy/bar_azure_foo.token")

    try:
        generate_and_write_feedstock_token(user, repo, ci=ci)

        assert os.path.exists(pth)
        assert not os.path.exists(opth)

        if ci is not None:
            generate_and_write_feedstock_token(user, repo, ci=None)
        else:
            generate_and_write_feedstock_token(user, repo, ci="azure")

        # we cannot do it twice
        with pytest.raises(FeedstockTokenError):
            generate_and_write_feedstock_token(user, repo, ci=ci)
    finally:
        if os.path.exists(pth):
            os.remove(pth)
        if os.path.exists(opth):
            os.remove(opth)


@pytest.mark.parametrize("ci", [None, "azure"])
def test_read_feedstock_token(ci):
    user = "bar"
    repo = "foo"
    if ci:
        pth = os.path.expanduser("~/.conda-smithy/bar_%s_foo.token" % ci)
    else:
        pth = os.path.expanduser("~/.conda-smithy/bar_foo.token")

    # no token
    token, err = read_feedstock_token(user, repo, ci=ci)
    assert "No token found in" in err
    assert token is None

    # empty
    try:
        os.system("touch " + pth)
        token, err = read_feedstock_token(user, repo, ci=ci)
        assert "Empty token found in" in err
        assert token is None
    finally:
        if os.path.exists(pth):
            os.remove(pth)

    # token ok
    try:
        generate_and_write_feedstock_token(user, repo, ci=ci)
        token, err = read_feedstock_token(user, repo, ci=ci)
        assert err is None
        assert token is not None

        if ci is not None:
            token, err = read_feedstock_token(user, repo, ci=None)
        else:
            token, err = read_feedstock_token(user, repo, ci="azure")
        assert "No token found in" in err
        assert token is None
    finally:
        if os.path.exists(pth):
            os.remove(pth)


@pytest.mark.parametrize("status_code", [200, 404])
@pytest.mark.parametrize(
    "token_data", [{"tokens": ["blah"]}, {}, {"tokens": []}]
)
@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo",
    [
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens",
    ],
)
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_token_exists(
    gh_mock,
    repo,
    project,
    ci,
    requests_mock,
    token_data,
    status_code,
):
    gh_mock.return_value = "abc123"

    user = "foo"
    reg_pth = feedstock_token_repo_path(project, ci=ci)
    if status_code == 200 and (
        len(token_data) == 0
        or ("tokens" in token_data and len(token_data["tokens"]) > 0)
    ):
        retval = True
    else:
        retval = False
    requests_mock.get(
        "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
        % reg_pth,
        status_code=status_code,
        json={
            "encoding": "base64",
            "content": base64.standard_b64encode(
                json.dumps(token_data).encode("utf-8")
            ).decode("ascii"),
        },
    )

    assert feedstock_token_exists(user, project, repo, ci=ci) is retval
    assert requests_mock.call_count == 1
    assert (
        requests_mock.request_history[-1].headers["Authorization"]
        == "Bearer abc123"
    )


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo",
    [
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens",
    ],
)
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_token_raises(
    gh_mock,
    repo,
    project,
    ci,
    requests_mock,
):
    gh_mock.return_value = "abc123"
    user = "foo"
    reg_pth = feedstock_token_repo_path(project, ci=ci)
    requests_mock.get(
        "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
        % reg_pth,
        status_code=500,
    )

    with pytest.raises(FeedstockTokenError) as e:
        feedstock_token_exists(user, project, repo, ci=ci)

    assert "Fetching feedstock token" in str(e.value)
    assert requests_mock.call_count == 1
    assert (
        requests_mock.request_history[-1].headers["Authorization"]
        == "Bearer abc123"
    )


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo",
    [
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git/",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens.git",
        "https://${GITHUB_TOKEN}@github.com/foo/feedstock-tokens",
    ],
)
@mock.patch("conda_smithy.feedstock_tokens.secrets")
@mock.patch("conda_smithy.feedstock_tokens.os.urandom")
@mock.patch("conda_smithy.github.gh_token")
def test_register_feedstock_token_works(
    gh_mock,
    osuran_mock,
    secrets_mock,
    repo,
    project,
    ci,
    requests_mock,
):
    gh_mock.return_value = "abc123"
    secrets_mock.token_hex.return_value = "fgh"
    osuran_mock.return_value = b"\x80SA"

    user = "foo"
    pth = feedstock_token_local_path(user, project, ci=ci)
    reg_pth = feedstock_token_repo_path(project, ci=ci)
    try:
        generate_and_write_feedstock_token(user, project, ci=ci)

        requests_mock.get(
            "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
            % reg_pth,
            status_code=404,
        )
        requests_mock.put(
            "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
            % reg_pth,
            status_code=201,
        )

        register_feedstock_token(user, project, repo, ci=ci)
    finally:
        if os.path.exists(pth):
            os.remove(pth)

    assert requests_mock.call_count == 2
    assert (
        requests_mock.request_history[-2].headers["Authorization"]
        == "Bearer abc123"
    )
    assert (
        requests_mock.request_history[-1].headers["Authorization"]
        == "Bearer abc123"
    )

    assert requests_mock.request_history[-1].json()["message"] == (
        "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** "
        "added token for %s/%s on CI%s"
        % (user, project, "" if ci is None else " " + ci)
    )

    salted_token = scrypt.hash("fgh", b"\x80SA", buflen=256)
    token_data = {
        "tokens": [
            {
                "salt": b"\x80SA".hex(),
                "hashed_token": salted_token.hex(),
            }
        ],
    }
    content = base64.standard_b64encode(
        json.dumps(token_data).encode("utf-8")
    ).decode("ascii")
    assert requests_mock.request_history[-1].json()["content"] == content


@pytest.mark.parametrize(
    "repo", ["$GITHUB_TOKEN", "${GITHUB_TOKEN}", "$GH_TOKEN", "${GH_TOKEN}"]
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
    pth = os.path.expanduser("~/.conda-smithy/foo_bar.token")
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
    "repo", ["$GITHUB_TOKEN", "${GITHUB_TOKEN}", "$GH_TOKEN", "${GH_TOKEN}"]
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
    pth = os.path.expanduser("~/.conda-smithy/foo_bar.token")
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

    git_mock.Repo.clone_from.assert_called_once_with(
        "abc123",
        str(tmpdir),
        depth=1,
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
@pytest.mark.parametrize("github_actions", [True, False])
@pytest.mark.parametrize("clobber", [True, False])
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
@mock.patch(
    "conda_smithy.feedstock_tokens.add_feedstock_token_to_github_actions"
)
def test_register_feedstock_token_with_providers(
    github_actions_mock,
    azure_mock,
    travis_mock,
    circle_mock,
    drone_mock,
    drone,
    circle,
    azure,
    travis,
    github_actions,
    clobber,
):
    user = "foo"
    project = "bar"

    pth = os.path.expanduser("~/.conda-smithy/foo_bar.token")

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
            github_actions=github_actions,
            clobber=clobber,
            drone_endpoints=[drone_default_endpoint],
        )

        if drone:
            drone_mock.assert_called_once_with(
                user,
                project,
                feedstock_token,
                clobber,
                drone_default_endpoint,
            )
        else:
            drone_mock.assert_not_called()

        if circle:
            circle_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            circle_mock.assert_not_called()

        if travis:
            travis_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            travis_mock.assert_not_called()

        if azure:
            azure_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            azure_mock.assert_not_called()

        if github_actions:
            github_actions_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            github_actions_mock.assert_not_called()
    finally:
        if os.path.exists(pth):
            os.remove(pth)


@pytest.mark.parametrize("drone", [True, False])
@pytest.mark.parametrize("circle", [True, False])
@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("travis", [True, False])
@pytest.mark.parametrize("github_actions", [True, False])
@pytest.mark.parametrize("clobber", [True, False])
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
@mock.patch(
    "conda_smithy.feedstock_tokens.add_feedstock_token_to_github_actions"
)
def test_register_feedstock_token_with_proviers_notoken(
    github_actions_mock,
    azure_mock,
    travis_mock,
    circle_mock,
    drone_mock,
    drone,
    circle,
    azure,
    travis,
    github_actions,
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
            github_actions=github_actions,
            clobber=clobber,
        )

    assert "No token" in str(e.value)

    drone_mock.assert_not_called()
    circle_mock.assert_not_called()
    travis_mock.assert_not_called()
    azure_mock.assert_not_called()
    github_actions_mock.assert_not_called()


@pytest.mark.parametrize(
    "provider", ["drone", "circle", "travis", "azure", "github actions"]
)
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
@mock.patch(
    "conda_smithy.feedstock_tokens.add_feedstock_token_to_github_actions"
)
def test_register_feedstock_token_with_proviers_error(
    github_actions_mock,
    azure_mock,
    travis_mock,
    circle_mock,
    drone_mock,
    provider,
):
    user = "foo"
    project = "bar-feedstock"

    pth = os.path.expanduser("~/.conda-smithy/foo_bar-feedstock.token")

    if provider == "drone":
        drone_mock.side_effect = ValueError("blah")
    if provider == "circle":
        circle_mock.side_effect = ValueError("blah")
    if provider == "travis":
        travis_mock.side_effect = ValueError("blah")
    if provider == "azure":
        azure_mock.side_effect = ValueError("blah")
    if provider == "github actions":
        github_actions_mock.side_effect = ValueError("blah")

    try:
        generate_and_write_feedstock_token(user, project)
        feedstock_token, _ = read_feedstock_token(user, project)

        with pytest.raises(RuntimeError) as e:
            register_feedstock_token_with_proviers(
                user, project, drone_endpoints=[drone_default_endpoint]
            )

        assert "on %s" % provider in str(e.value)
    finally:
        if os.path.exists(pth):
            os.remove(pth)
