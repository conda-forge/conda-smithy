import json
import os
import time
from unittest import mock

import pytest
import scrypt

from conda_smithy.ci_register import drone_default_endpoint
from conda_smithy.feedstock_tokens import (
    FeedstockTokenError,
    feedstock_token_exists,
    feedstock_token_local_path,
    generate_and_write_feedstock_token,
    is_valid_feedstock_token,
    read_feedstock_token,
    register_feedstock_token,
    register_feedstock_token_with_providers,
)


@pytest.mark.parametrize(
    "provider,ci,retval_ci",
    [
        (None, None, True),  # generic token so OK
        (None, "azure", True),  # generic token w/ CI so OK
        ("azure", None, False),  # provider-specific token w/o CI so not OK
        (
            "azure",
            "azure",
            True,
        ),  # provider-specific token w/ correct CI so OK
        (
            "azure",
            "blah",
            False,
        ),  # provider-specific token w/ wrong CI so not OK
    ],
)
@pytest.mark.parametrize(
    "expires_at,retval_time",
    [
        (time.time() + 1e4, True),  # expires in the future so OK
        (time.time() - 1e4, False),  # expired in the past so not OK
    ],
)
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_tokens_roundtrip(
    gh_mock,
    git_mock,
    tmp_mock,
    tmpdir,
    repo,
    project,
    provider,
    ci,
    retval_ci,
    expires_at,
    retval_time,
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )

    user = "foo"
    pth = feedstock_token_local_path(
        user,
        project,
        provider=ci,
    )
    token_json_pth = os.path.join(tmpdir, "tokens", f"{project}.json")
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)

    try:
        generate_and_write_feedstock_token(user, project, provider=ci)
        assert os.path.exists(pth)

        register_feedstock_token(user, project, repo, provider=ci)
        assert os.path.exists(token_json_pth)

        with open(token_json_pth) as fp:
            token_data = json.load(fp)
        if provider is not None:
            token_data["tokens"][0]["provider"] = provider
        if expires_at is not None:
            token_data["tokens"][0]["expires_at"] = expires_at
        with open(token_json_pth, "w") as fp:
            fp.write(json.dumps(token_data))

        with open(pth) as fp:
            feedstock_token = fp.read().strip()

        retval = is_valid_feedstock_token(
            user, project, feedstock_token, repo, provider=ci
        )
    finally:
        if os.path.exists(pth):
            os.remove(pth)
        if os.path.exists(token_json_pth):
            os.remove(token_json_pth)

    assert retval is (retval_ci and retval_time)


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_is_valid_feedstock_token_nofile(
    gh_mock,
    git_mock,
    tmp_mock,
    tmpdir,
    repo,
    project,
    ci,
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )

    user = "conda-forge"
    feedstock_token = "akdjhfl"
    retval = is_valid_feedstock_token(
        user, project, feedstock_token, repo, provider=ci
    )
    assert not retval


@pytest.mark.parametrize(
    "provider,ci",
    [
        (None, None),
        (None, "azure"),
        ("azure", None),
        ("azure", "azure"),
        ("azure", "blah"),
    ],
)
@pytest.mark.parametrize(
    "expires_at",
    [(time.time() + 1e4), (time.time() - 1e4)],
)
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo", ["GITHUB_TOKEN", "${GITHUB_TOKEN}", "GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_is_valid_feedstock_token_badtoken(
    gh_mock,
    git_mock,
    tmp_mock,
    tmpdir,
    repo,
    project,
    expires_at,
    provider,
    ci,
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )

    user = "conda-forge"
    feedstock_token = "akdjhfl"

    token_pth = os.path.join(tmpdir, "tokens", f"{project}.json")
    os.makedirs(os.path.dirname(token_pth), exist_ok=True)
    with open(token_pth, "w") as fp:
        td = {"salt": b"adf".hex(), "hashed_token": b"fgh".hex()}
        if provider is not None:
            td["provider"] = provider
        if expires_at is not None:
            td["expires_at"] = expires_at
        json.dump({"tokens": [td]}, fp)

    retval = is_valid_feedstock_token(
        user, project, feedstock_token, repo, provider=ci
    )
    assert not retval


@pytest.mark.parametrize("ci", [None, "azure"])
def test_generate_and_write_feedstock_token(ci):
    user = "bar"
    repo = "foo"

    if ci:
        pth = os.path.expanduser(f"~/.conda-smithy/bar_foo_{ci}.token")
        opth = os.path.expanduser("~/.conda-smithy/bar_foo.token")
    else:
        pth = os.path.expanduser("~/.conda-smithy/bar_foo.token")
        opth = os.path.expanduser("~/.conda-smithy/bar_foo_azure.token")

    try:
        generate_and_write_feedstock_token(user, repo, provider=ci)

        assert not os.path.exists(opth)
        assert os.path.exists(pth)

        if ci is not None:
            generate_and_write_feedstock_token(user, repo, provider=None)
        else:
            generate_and_write_feedstock_token(user, repo, provider="azure")

        # we cannot do it twice
        with pytest.raises(FeedstockTokenError):
            generate_and_write_feedstock_token(user, repo, provider=ci)
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
        pth = os.path.expanduser(f"~/.conda-smithy/bar_foo_{ci}.token")
    else:
        pth = os.path.expanduser("~/.conda-smithy/bar_foo.token")

    # no token
    token, err = read_feedstock_token(user, repo, provider=ci)
    assert "No token found in" in err
    assert token is None

    # empty
    try:
        os.system("touch " + pth)
        token, err = read_feedstock_token(user, repo, provider=ci)
        assert "Empty token found in" in err
        assert token is None
    finally:
        if os.path.exists(pth):
            os.remove(pth)

    # token ok
    try:
        generate_and_write_feedstock_token(user, repo, provider=ci)
        token, err = read_feedstock_token(user, repo, provider=ci)
        assert err is None
        assert token is not None

        if ci is not None:
            token, err = read_feedstock_token(user, repo, provider=None)
        else:
            token, err = read_feedstock_token(user, repo, provider="azure")
        assert "No token found in" in err
        assert token is None
    finally:
        if os.path.exists(pth):
            os.remove(pth)


@pytest.mark.parametrize(
    "provider,ci,retval_ci",
    [
        (None, None, True),  # generic token so OK
        (None, "azure", True),  # generic token w/ CI so OK
        ("azure", None, False),  # provider-specific token w/o CI so not OK
        (
            "azure",
            "azure",
            True,
        ),  # provider-specific token w/ correct CI so OK
        (
            "azure",
            "blah",
            False,
        ),  # provider-specific token w/ wrong CI so not OK
    ],
)
@pytest.mark.parametrize(
    "expires_at,retval_time",
    [
        (time.time() + 1e4, True),  # expires in the future so OK
        (time.time() - 1e4, False),  # expired in the past so not OK
    ],
)
@pytest.mark.parametrize("file_exists", [True, False])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo", ["$GITHUB_TOKEN", "${GITHUB_TOKEN}", "$GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_token_exists(
    gh_mock,
    git_mock,
    tmp_mock,
    tmpdir,
    repo,
    project,
    file_exists,
    ci,
    provider,
    retval_ci,
    expires_at,
    retval_time,
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )

    user = "foo"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    if file_exists:
        with open(
            os.path.join(tmpdir, "tokens", f"{project}.json"), "w"
        ) as fp:
            data = {"tokens": [{}]}
            if provider is not None:
                data["tokens"][0]["provider"] = provider
            if expires_at is not None:
                data["tokens"][0]["expires_at"] = expires_at
            fp.write(json.dumps(data))

    _retval = file_exists and retval_time and retval_ci

    assert feedstock_token_exists(user, project, repo, provider=ci) is _retval

    git_mock.Repo.clone_from.assert_called_once_with(
        "abc123",
        str(tmpdir),
        depth=1,
    )


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize("project", ["bar", "bar-feedstock"])
@pytest.mark.parametrize(
    "repo", ["$GITHUB_TOKEN", "${GITHUB_TOKEN}", "$GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_feedstock_token_raises(
    gh_mock, git_mock, tmp_mock, tmpdir, repo, project, ci
):
    gh_mock.return_value = "abc123"
    tmp_mock.TemporaryDirectory.return_value.__enter__.return_value = str(
        tmpdir
    )

    git_mock.Repo.clone_from.side_effect = ValueError("blarg")
    user = "foo"
    os.makedirs(os.path.join(tmpdir, "tokens"), exist_ok=True)
    with open(os.path.join(tmpdir, "tokens", f"{project}.json"), "w") as fp:
        fp.write("{}")

    with pytest.raises(FeedstockTokenError) as e:
        feedstock_token_exists(user, project, repo, provider=ci)

    assert "Testing for the feedstock token for" in str(e.value)

    git_mock.Repo.clone_from.assert_called_once_with(
        "abc123",
        str(tmpdir),
        depth=1,
    )


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize(
    "repo", ["$GITHUB_TOKEN", "${GITHUB_TOKEN}", "$GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.secrets")
@mock.patch("conda_smithy.feedstock_tokens.os.urandom")
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_register_feedstock_token_works(
    gh_mock,
    git_mock,
    tmp_mock,
    osuran_mock,
    secrets_mock,
    tmpdir,
    repo,
    ci,
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
    pth = feedstock_token_local_path(
        user,
        project,
        provider=ci,
    )
    token_json_pth = os.path.join(tmpdir, "tokens", f"{project}.json")

    try:
        generate_and_write_feedstock_token(user, project, provider=ci)

        register_feedstock_token(user, project, repo, provider=ci)

    finally:
        if os.path.exists(pth):
            os.remove(pth)

    git_mock.Repo.clone_from.assert_called_once_with(
        "abc123",
        str(tmpdir),
        depth=1,
    )

    repo = git_mock.Repo.clone_from.return_value
    repo.index.add.assert_called_once_with(token_json_pth)
    ci_or_empty = "" if ci is None else " " + ci
    repo.index.commit.assert_called_once_with(
        f"[ci skip] [skip ci] [cf admin skip] ***NO_CI*** added token for {user}/{project} on provider{ci_or_empty}"
    )
    repo.remote.return_value.pull.assert_called_once_with(rebase=True)
    repo.remote.return_value.push.assert_called_once_with()

    salted_token = scrypt.hash("fgh", b"\x80SA", buflen=256)
    data = {
        "salt": b"\x80SA".hex(),
        "hashed_token": salted_token.hex(),
    }
    if ci is not None:
        data["provider"] = ci

    with open(token_json_pth) as fp:
        assert json.load(fp) == {"tokens": [data]}


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize(
    "repo", ["$GITHUB_TOKEN", "${GITHUB_TOKEN}", "$GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.secrets")
@mock.patch("conda_smithy.feedstock_tokens.os.urandom")
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_register_feedstock_token_notoken(
    gh_mock,
    git_mock,
    tmp_mock,
    osuran_mock,
    secrets_mock,
    tmpdir,
    repo,
    ci,
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
    pth = feedstock_token_local_path(
        user,
        project,
        provider=ci,
    )
    token_json_pth = os.path.join(tmpdir, "tokens", "bar.json")

    try:
        with pytest.raises(FeedstockTokenError) as e:
            register_feedstock_token(user, project, repo, provider=ci)
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


@pytest.mark.parametrize("ci", [None, "azure"])
@pytest.mark.parametrize(
    "repo", ["$GITHUB_TOKEN", "${GITHUB_TOKEN}", "$GH_TOKEN", "${GH_TOKEN}"]
)
@mock.patch("conda_smithy.feedstock_tokens.secrets")
@mock.patch("conda_smithy.feedstock_tokens.os.urandom")
@mock.patch("conda_smithy.feedstock_tokens.tempfile")
@mock.patch("conda_smithy.feedstock_tokens.git")
@mock.patch("conda_smithy.github.gh_token")
def test_register_feedstock_token_append(
    gh_mock,
    git_mock,
    tmp_mock,
    osuran_mock,
    secrets_mock,
    tmpdir,
    repo,
    ci,
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
    pth = feedstock_token_local_path(
        user,
        project,
        provider=ci,
    )
    token_json_pth = os.path.join(tmpdir, "tokens", "bar.json")
    with open(token_json_pth, "w") as fp:
        fp.write('{"tokens": [1]}')

    try:
        generate_and_write_feedstock_token(user, project, provider=ci)
        register_feedstock_token(user, project, repo, provider=ci)
    finally:
        if os.path.exists(pth):
            os.remove(pth)

    git_mock.Repo.clone_from.assert_called_once_with(
        "abc123",
        str(tmpdir),
        depth=1,
    )

    repo = git_mock.Repo.clone_from.return_value
    repo.index.add.assert_called_once_with(token_json_pth)
    ci_or_empty = "" if ci is None else " " + ci
    repo.index.commit.assert_called_once_with(
        f"[ci skip] [skip ci] [cf admin skip] ***NO_CI*** added token for {user}/{project} on provider{ci_or_empty}"
    )
    repo.remote.return_value.pull.assert_called_once_with(rebase=True)
    repo.remote.return_value.push.assert_called_once_with()

    salted_token = scrypt.hash("fgh", b"\x80SA", buflen=256)
    data = {
        "salt": b"\x80SA".hex(),
        "hashed_token": salted_token.hex(),
    }
    if ci is not None:
        data["provider"] = ci

    with open(token_json_pth) as fp:
        assert json.load(fp) == {"tokens": [1, data]}


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
        for provider in providers:
            generate_and_write_feedstock_token(
                user, project, provider=provider
            )

        register_feedstock_token_with_providers(
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
                feedstock_token, _ = read_feedstock_token(
                    user, project, provider="drone"
                )
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
                feedstock_token, _ = read_feedstock_token(
                    user, project, provider="circle"
                )
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

            circle_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            circle_mock.assert_not_called()

        if travis:
            if unique_token_per_provider:
                feedstock_token, _ = read_feedstock_token(
                    user, project, provider="travis"
                )
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

            travis_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            travis_mock.assert_not_called()

        if azure:
            if unique_token_per_provider:
                feedstock_token, _ = read_feedstock_token(
                    user, project, provider="azure"
                )
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

            azure_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            azure_mock.assert_not_called()

        if github_actions:
            if unique_token_per_provider:
                feedstock_token, _ = read_feedstock_token(
                    user, project, provider="github_actions"
                )
            else:
                feedstock_token, _ = read_feedstock_token(user, project)

            github_actions_mock.assert_called_once_with(
                user, project, feedstock_token, clobber
            )
        else:
            github_actions_mock.assert_not_called()
    finally:
        for provider in providers:
            pth = feedstock_token_local_path(user, project, provider=provider)
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
def test_register_feedstock_token_with_providers_notoken(
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

    if any([drone, circle, travis, azure, github_actions]):
        with pytest.raises(FeedstockTokenError) as e:
            register_feedstock_token_with_providers(
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
    "provider", ["drone", "circle", "travis", "azure", "github_actions"]
)
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
@mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
@mock.patch(
    "conda_smithy.feedstock_tokens.add_feedstock_token_to_github_actions"
)
def test_register_feedstock_token_with_providers_error(
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
    if provider == "github_actions":
        github_actions_mock.side_effect = ValueError("blah")

    try:
        for _provider in providers:
            generate_and_write_feedstock_token(
                user, project, provider=_provider
            )

        with pytest.raises(FeedstockTokenError) as e:
            register_feedstock_token_with_providers(
                user,
                project,
                drone_endpoints=[drone_default_endpoint],
                unique_token_per_provider=unique_token_per_provider,
            )

        assert f"on {provider}" in str(e.value)
    finally:
        for _provider in providers:
            pth = feedstock_token_local_path(user, project, provider=_provider)
            if os.path.exists(pth):
                os.remove(pth)
