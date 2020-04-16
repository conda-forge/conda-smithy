import os
from unittest import mock

import pytest

from conda_smithy.anaconda_token_rotation import rotate_anaconda_token


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
def test_register_feedstock_token_with_proviers(
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
    tmpdir,
):
    user = "foo"
    project = "bar"

    monkeypatch.setenv("BINSTAR_TOKEN", "abc123")

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
        drone_mock.assert_called_once_with(
            user, project, "abc123"
        )
    else:
        drone_mock.assert_not_called()

    if circle:
        circle_mock.assert_called_once_with(
            user, project, "abc123"
        )
    else:
        circle_mock.assert_not_called()

    if travis:
        travis_mock.assert_called_once_with(
            user, project, "abc123"
        )
    else:
        travis_mock.assert_not_called()

    if azure:
        azure_mock.assert_called_once_with(
            user, project, "abc123"
        )
    else:
        azure_mock.assert_not_called()

    if appveyor:
        appveyor_mock.assert_called_once_with(
            user, project, "abc", "abc123"
        )
    else:
        appveyor_mock.assert_not_called()


# @pytest.mark.parametrize("drone", [True, False])
# @pytest.mark.parametrize("circle", [True, False])
# @pytest.mark.parametrize("azure", [True, False])
# @pytest.mark.parametrize("travis", [True, False])
# @pytest.mark.parametrize("clobber", [True, False])
# @mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
# @mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
# @mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
# @mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
# def test_register_feedstock_token_with_proviers_notoken(
#     azure_mock,
#     travis_mock,
#     circle_mock,
#     drone_mock,
#     drone,
#     circle,
#     travis,
#     azure,
#     clobber,
# ):
#     user = "foo"
#     project = "bar"
#
#     with pytest.raises(RuntimeError) as e:
#         register_feedstock_token_with_proviers(
#             user,
#             project,
#             drone=drone,
#             circle=circle,
#             travis=travis,
#             azure=azure,
#             clobber=clobber,
#         )
#
#     assert "No token" in str(e.value)
#
#     drone_mock.assert_not_called()
#     circle_mock.assert_not_called()
#     travis_mock.assert_not_called()
#     azure_mock.assert_not_called()
#
#
# @pytest.mark.parametrize("provider", ["drone", "circle", "travis", "azure"])
# @mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_drone")
# @mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_circle")
# @mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_travis")
# @mock.patch("conda_smithy.feedstock_tokens.add_feedstock_token_to_azure")
# def test_register_feedstock_token_with_proviers_error(
#     azure_mock, travis_mock, circle_mock, drone_mock, provider,
# ):
#     user = "foo"
#     project = "bar-feedstock"
#
#     pth = os.path.expanduser("~/.conda-smithy/foo_bar_feedstock.token")
#
#     if provider == "drone":
#         drone_mock.side_effect = ValueError("blah")
#     if provider == "circle":
#         circle_mock.side_effect = ValueError("blah")
#     if provider == "travis":
#         travis_mock.side_effect = ValueError("blah")
#     if provider == "azure":
#         azure_mock.side_effect = ValueError("blah")
#
#     try:
#         generate_and_write_feedstock_token(user, project)
#         feedstock_token, _ = read_feedstock_token(user, project)
#
#         with pytest.raises(RuntimeError) as e:
#             register_feedstock_token_with_proviers(
#                 user, project,
#             )
#
#         assert "on %s" % provider in str(e.value)
#     finally:
#         if os.path.exists(pth):
#             os.remove(pth)
