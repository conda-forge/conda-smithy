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
def test_register_feedstock_token_notoken(
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

        with pytest.raises(FeedstockTokenError) as e:
            register_feedstock_token(user, project, repo, ci=ci)
    finally:
        if os.path.exists(pth):
            os.remove(pth)

    assert requests_mock.call_count == 1
    assert (
        requests_mock.request_history[-1].headers["Authorization"]
        == "Bearer abc123"
    )
    assert "No token found in" in str(e.value)


@pytest.mark.parametrize("append", [True, False])
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
def test_register_feedstock_token_exists_already(
    gh_mock,
    osuran_mock,
    secrets_mock,
    repo,
    project,
    ci,
    requests_mock,
    append,
):
    gh_mock.return_value = "abc123"
    secrets_mock.token_hex.return_value = "fgh"
    osuran_mock.return_value = b"\x80SA"

    old_salted_token = scrypt.hash("fghk", b"\x80SA", buflen=256)
    old_token_data = {
        "tokens": [
            {
                "salt": b"\x80SA".hex(),
                "hashed_token": old_salted_token.hex(),
            }
        ],
    }
    old_content = base64.standard_b64encode(
        json.dumps(old_token_data).encode("utf-8")
    ).decode("ascii")

    user = "foo"
    pth = feedstock_token_local_path(user, project, ci=ci)
    reg_pth = feedstock_token_repo_path(project, ci=ci)
    try:
        generate_and_write_feedstock_token(user, project, ci=ci)

        requests_mock.get(
            "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
            % reg_pth,
            status_code=200,
            json={
                "encoding": "base64",
                "content": old_content,
                "sha": "blah",
            },
        )
        requests_mock.put(
            "https://api.github.com/repos/foo/feedstock-tokens/contents/%s"
            % reg_pth,
            status_code=201,
        )

        if not append:
            with pytest.raises(FeedstockTokenError) as e:
                register_feedstock_token(
                    user, project, repo, ci=ci, append=append
                )
        else:
            register_feedstock_token(user, project, repo, ci=ci, append=append)
    finally:
        if os.path.exists(pth):
            os.remove(pth)

    if append:
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
                old_token_data["tokens"][0],
                {
                    "salt": b"\x80SA".hex(),
                    "hashed_token": salted_token.hex(),
                },
            ],
        }
        content = base64.standard_b64encode(
            json.dumps(token_data).encode("utf-8")
        ).decode("ascii")
        assert requests_mock.request_history[-1].json()["content"] == content
    else:
        assert requests_mock.call_count == 1
        assert (
            requests_mock.request_history[-1].headers["Authorization"]
            == "Bearer abc123"
        )
        assert "Token for repo foo/%s on CI" % project in str(e.value)


@pytest.mark.parametrize("unique_token_per_provider", [False, True])
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
    unique_token_per_provider,
):
    user = "foo"
    project = "bar"
    providers = [
        None,
        "azure",
        "travis",
        "circle",
        "drone",
        "github_actions",
    ]

    try:
        for provier in providers:
            generate_and_write_feedstock_token(user, project, ci=provier)

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
            unique_token_per_provider=unique_token_per_provider,
        )

        if drone:
            if unique_token_per_provider:
                feedstock_token, _ = read_feedstock_token(user, project, ci="drone")
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

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
            if unique_token_per_provider:
                feedstock_token, _ = read_feedstock_token(user, project, ci="circle")
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

            circle_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            circle_mock.assert_not_called()

        if travis:
            if unique_token_per_provider:
                feedstock_token, _ = read_feedstock_token(user, project, ci="travis")
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

            travis_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            travis_mock.assert_not_called()

        if azure:
            if unique_token_per_provider:
                feedstock_token, _ = read_feedstock_token(user, project, ci="azure")
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

            azure_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            azure_mock.assert_not_called()

        if github_actions:
            if unique_token_per_provider:
                feedstock_token, _ = read_feedstock_token(user, project, ci="github_actions")
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

            github_actions_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            github_actions_mock.assert_not_called()
    finally:
        for provier in providers:
            pth = feedstock_token_local_path(user, project, ci=provier)
            if os.path.exists(pth):
                os.remove(pth)


@pytest.mark.parametrize("unique_token_per_provider", [False, True])
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
    unique_token_per_provider,
):
    user = "foo"
    project = "bar"

    if not any([drone, circle, travis, azure, github_actions]) and unique_token_per_provider:
        # we do not attempt to read or do any thing here so no error is raised
        pass
    else:
        with pytest.raises(FeedstockTokenError) as e:
            register_feedstock_token_with_proviers(
                user,
                project,
                drone=drone,
                circle=circle,
                travis=travis,
                azure=azure,
                github_actions=github_actions,
                clobber=clobber,
                unique_token_per_provider=unique_token_per_provider,
            )

        assert "No token" in str(e.value)

    drone_mock.assert_not_called()
    circle_mock.assert_not_called()
    travis_mock.assert_not_called()
    azure_mock.assert_not_called()
    github_actions_mock.assert_not_called()


@pytest.mark.parametrize("unique_token_per_provider", [False, True])
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
    unique_token_per_provider,
):
    user = "foo"
    project = "bar-feedstock"
    providers = [
        None,
        "azure",
        "travis",
        "circle",
        "drone",
        "github_actions",
    ]

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
        for provier in providers:
            generate_and_write_feedstock_token(user, project, ci=provier)

        with pytest.raises(FeedstockTokenError) as e:
            register_feedstock_token_with_proviers(
                user, project, drone_endpoints=[drone_default_endpoint],
                unique_token_per_provider=unique_token_per_provider,
            )

        assert "on %s" % provider in str(e.value)
    finally:
        for provier in providers:
            pth = feedstock_token_local_path(user, project, ci=provier)
            if os.path.exists(pth):
                os.remove(pth)
