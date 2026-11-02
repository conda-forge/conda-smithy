from unittest import mock

import pytest

from conda_smithy.anaconda_token_rotation import rotate_anaconda_token


@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("github_actions", [True, False])
@mock.patch("conda_smithy.github.gh_token")
@mock.patch("conda_smithy.anaconda_token_rotation._get_anaconda_token")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_azure")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_github_actions")
def test_rotate_anaconda_token(
    github_actions_mock,
    azure_mock,
    get_ac_token,
    get_gh_token,
    azure,
    github_actions,
):
    user = "foo"
    project = "bar"

    anaconda_token = "abc123"
    get_ac_token.return_value = anaconda_token
    get_gh_token.return_value = None

    feedstock_config_path = "abc/conda-forge.yml"

    rotate_anaconda_token(
        user,
        project,
        feedstock_config_path,
        azure=azure,
        github_actions=github_actions,
        token_name="MY_FANCY_TOKEN",
    )

    if azure:
        azure_mock.assert_called_once_with(
            user, project, anaconda_token, "MY_FANCY_TOKEN"
        )
    else:
        azure_mock.assert_not_called()

    if github_actions:
        github_actions_mock.assert_called_once_with(
            user,
            project,
            anaconda_token,
            "MY_FANCY_TOKEN",
            mock.ANY,
        )
    else:
        github_actions_mock.assert_not_called()


@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("github_actions", [True, False])
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_azure")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_github_actions")
def test_rotate_anaconda_token_notoken(
    github_actions_mock,
    azure_mock,
    azure,
    github_actions,
    monkeypatch,
):
    user = "foo"
    project = "bar"

    with pytest.raises(RuntimeError) as e:
        rotate_anaconda_token(
            user,
            project,
            None,
            azure=azure,
            github_actions=github_actions,
        )

    assert "anaconda token" in str(e.value)

    azure_mock.assert_not_called()
    github_actions_mock.assert_not_called()


@pytest.mark.parametrize(
    "provider",
    ["azure", "github_actions"],
)
@mock.patch("conda_smithy.github.gh_token")
@mock.patch("conda_smithy.anaconda_token_rotation._get_anaconda_token")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_azure")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_github_actions")
def test_rotate_anaconda_token_provider_error(
    github_actions_mock,
    azure_mock,
    get_ac_token,
    get_gh_token,
    provider,
):
    user = "foo"
    project = "bar"

    anaconda_token = "abc123"
    get_ac_token.return_value = anaconda_token
    get_gh_token.return_value = None

    user = "foo"
    project = "bar-feedstock"

    if provider == "azure":
        azure_mock.side_effect = ValueError("blah")
    if provider == "github_actions":
        github_actions_mock.side_effect = ValueError("blah")

    with pytest.raises(RuntimeError) as e:
        rotate_anaconda_token(user, project, None)

    assert "on {}".format(provider.replace("_", " ")) in str(e.value)
