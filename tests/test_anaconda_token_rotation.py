from unittest import mock

import pytest

from conda_smithy.anaconda_token_rotation import rotate_anaconda_token


@pytest.mark.parametrize("appveyor", [True, False])
@pytest.mark.parametrize("drone", [True, False])
@pytest.mark.parametrize("circle", [True, False])
@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("travis", [True, False])
@mock.patch("conda_smithy.anaconda_token_rotation._get_anaconda_token")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_appveyor")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_drone")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_circle")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_travis")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_azure")
def test_rotate_anaconda_token(
    azure_mock,
    travis_mock,
    circle_mock,
    drone_mock,
    appveyor_mock,
    get_ac_token,
    appveyor,
    drone,
    circle,
    travis,
    azure,
):
    user = "foo"
    project = "bar"

    anaconda_token = "abc123"
    get_ac_token.return_value = anaconda_token

    rotate_anaconda_token(
        user,
        project,
        "abc",
        drone=drone,
        circle=circle,
        travis=travis,
        azure=azure,
        appveyor=appveyor,
    )

    if drone:
        drone_mock.assert_called_once_with(user, project, anaconda_token)
    else:
        drone_mock.assert_not_called()

    if circle:
        circle_mock.assert_called_once_with(user, project, anaconda_token)
    else:
        circle_mock.assert_not_called()

    if travis:
        travis_mock.assert_called_once_with(user, project, anaconda_token)
    else:
        travis_mock.assert_not_called()

    if azure:
        azure_mock.assert_called_once_with(user, project, anaconda_token)
    else:
        azure_mock.assert_not_called()

    if appveyor:
        appveyor_mock.assert_called_once_with("abc", anaconda_token)
    else:
        appveyor_mock.assert_not_called()


@pytest.mark.parametrize("appveyor", [True, False])
@pytest.mark.parametrize("drone", [True, False])
@pytest.mark.parametrize("circle", [True, False])
@pytest.mark.parametrize("azure", [True, False])
@pytest.mark.parametrize("travis", [True, False])
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_appveyor")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_drone")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_circle")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_travis")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_azure")
def test_rotate_anaconda_token_notoken(
    azure_mock,
    travis_mock,
    circle_mock,
    drone_mock,
    appveyor_mock,
    appveyor,
    drone,
    circle,
    travis,
    azure,
    monkeypatch,
):
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
        )

    assert "anaconda token" in str(e.value)

    drone_mock.assert_not_called()
    circle_mock.assert_not_called()
    travis_mock.assert_not_called()
    azure_mock.assert_not_called()
    appveyor_mock.assert_not_called()


@pytest.mark.parametrize(
    "provider", ["drone", "circle", "travis", "azure", "appveyor"]
)
@mock.patch("conda_smithy.anaconda_token_rotation._get_anaconda_token")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_appveyor")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_drone")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_circle")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_travis")
@mock.patch("conda_smithy.anaconda_token_rotation.rotate_token_in_azure")
def test_rotate_anaconda_token_provier_error(
    azure_mock,
    travis_mock,
    circle_mock,
    drone_mock,
    appveyor_mock,
    get_ac_token,
    provider,
):
    user = "foo"
    project = "bar"

    anaconda_token = "abc123"
    get_ac_token.return_value = anaconda_token

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

    with pytest.raises(RuntimeError) as e:
        rotate_anaconda_token(user, project, None)

    assert "on %s" % provider in str(e.value)
