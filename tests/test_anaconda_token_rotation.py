import pytest

from conda_smithy.anaconda_token_rotation import rotate_anaconda_token

from conda_smithy.ci_register import drone_default_endpoint


@pytest.mark.parametrize("appveyor", [True, False])
@pytest.mark.parametrize("drone", [True, False])
@pytest.mark.parametrize("circle", [True, False])
@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("travis", [True, False])
@pytest.mark.parametrize("github_actions", [True, False])
def test_rotate_anaconda_token(
    mocker,
    appveyor,
    drone,
    circle,
    azure,
    travis,
    github_actions,
):
    github_actions_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_github_actions"
    )
    azure_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_azure"
    )
    travis_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_travis"
    )
    circle_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_circle"
    )
    drone_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_drone"
    )
    appveyor_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_appveyor"
    )
    get_ac_token = mocker.patch(
        "conda_smithy.anaconda_token_rotation._get_anaconda_token"
    )
    get_gh_token = mocker.patch("conda_smithy.github.gh_token")

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
        drone=drone,
        circle=circle,
        travis=travis,
        azure=azure,
        appveyor=appveyor,
        github_actions=github_actions,
        token_name="MY_FANCY_TOKEN",
        drone_endpoints=[drone_default_endpoint],
    )

    if drone:
        drone_mock.assert_called_once_with(
            user,
            project,
            anaconda_token,
            "MY_FANCY_TOKEN",
            drone_default_endpoint,
        )
    else:
        drone_mock.assert_not_called()

    if circle:
        circle_mock.assert_called_once_with(
            user, project, anaconda_token, "MY_FANCY_TOKEN"
        )
    else:
        circle_mock.assert_not_called()

    if travis:
        travis_mock.assert_called_once_with(
            user,
            project,
            feedstock_config_path,
            anaconda_token,
            "MY_FANCY_TOKEN",
        )
    else:
        travis_mock.assert_not_called()

    if azure:
        azure_mock.assert_called_once_with(
            user, project, anaconda_token, "MY_FANCY_TOKEN"
        )
    else:
        azure_mock.assert_not_called()

    if appveyor:
        appveyor_mock.assert_called_once_with(
            feedstock_config_path, anaconda_token, "MY_FANCY_TOKEN"
        )
    else:
        appveyor_mock.assert_not_called()

    if github_actions:
        github_actions_mock.assert_called_once_with(
            user,
            project,
            anaconda_token,
            "MY_FANCY_TOKEN",
            mocker.ANY,
        )
    else:
        github_actions_mock.assert_not_called()


@pytest.mark.parametrize("appveyor", [True, False])
@pytest.mark.parametrize("drone", [True, False])
@pytest.mark.parametrize("circle", [True, False])
@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("travis", [True, False])
@pytest.mark.parametrize("github_actions", [True, False])
def test_rotate_anaconda_token_notoken(
    mocker,
    appveyor,
    drone,
    circle,
    azure,
    travis,
    github_actions,
    snapshot,
):
    github_actions_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_github_actions"
    )
    azure_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_azure"
    )
    travis_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_travis"
    )
    circle_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_circle"
    )
    drone_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_drone"
    )
    appveyor_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_appveyor"
    )

    user = "foo"
    project = "bar"

    with pytest.raises(RuntimeError) as e:
        rotate_anaconda_token(
            user,
            project,
            None,
            drone=drone,
            circle=circle,
            travis=travis,
            azure=azure,
            appveyor=appveyor,
            github_actions=github_actions,
            drone_endpoints=[drone_default_endpoint],
        )
    assert str(e.value) == snapshot

    drone_mock.assert_not_called()
    circle_mock.assert_not_called()
    travis_mock.assert_not_called()
    azure_mock.assert_not_called()
    appveyor_mock.assert_not_called()
    github_actions_mock.assert_not_called()


@pytest.mark.parametrize(
    "provider",
    ["drone", "circle", "travis", "azure", "appveyor", "github_actions"],
)
def test_rotate_anaconda_token_provider_error(mocker, provider, snapshot):
    github_actions_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_github_actions"
    )
    azure_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_azure"
    )
    travis_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_travis"
    )
    circle_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_circle"
    )
    drone_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_drone"
    )
    appveyor_mock = mocker.patch(
        "conda_smithy.anaconda_token_rotation.rotate_token_in_appveyor"
    )
    get_ac_token = mocker.patch(
        "conda_smithy.anaconda_token_rotation._get_anaconda_token"
    )
    get_gh_token = mocker.patch("conda_smithy.github.gh_token")

    user = "foo"
    project = "bar"

    anaconda_token = "abc123"
    get_ac_token.return_value = anaconda_token
    get_gh_token.return_value = None

    user = "foo"
    project = "bar-feedstock"

    if provider == "drone":
        drone_mock.side_effect = ValueError("blah")
    if provider == "circle":
        circle_mock.side_effect = ValueError("blah")
    if provider == "travis":
        travis_mock.side_effect = ValueError("blah")
    if provider == "azure":
        azure_mock.side_effect = ValueError("blah")
    if provider == "appveyor":
        appveyor_mock.side_effect = ValueError("blah")
    if provider == "github_actions":
        github_actions_mock.side_effect = ValueError("blah")

    with pytest.raises(RuntimeError) as e:
        rotate_anaconda_token(
            user, project, None, drone_endpoints=[drone_default_endpoint]
        )
    assert str(e.value) == snapshot
