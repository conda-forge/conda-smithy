from typing import Union

import pytest
from conda_build.metadata import MetaData
from rattler_build_conda_compat.render import MetaData as RatlerBuildMetadata

from conda_smithy.utils import (
    RATTLER_BUILD,
    _get_metadata_from_feedstock_dir,
    conditional_value_any_matches,
    get_feedstock_name_from_meta,
)


def test_get_metadata_from_feedstock_dir(noarch_recipe):
    feedstock_dir = noarch_recipe[0]

    build_tool = noarch_recipe[1]["conda_build_tool"]
    metadata = _get_metadata_from_feedstock_dir(feedstock_dir, noarch_recipe[1])

    expected_metadata_type = (
        RatlerBuildMetadata if build_tool == RATTLER_BUILD else MetaData
    )

    assert isinstance(metadata, expected_metadata_type)


def test_get_metadata_from_feedstock_dir_jinja2(noarch_recipe_with_python_min):
    feedstock_dir = noarch_recipe_with_python_min[0]

    build_tool = noarch_recipe_with_python_min[1]["conda_build_tool"]
    metadata = _get_metadata_from_feedstock_dir(
        feedstock_dir,
        noarch_recipe_with_python_min[1],
        conda_forge_pinning_file=noarch_recipe_with_python_min[1][
            "exclusive_config_file"
        ],
    )

    expected_metadata_type = (
        RatlerBuildMetadata if build_tool == RATTLER_BUILD else MetaData
    )

    if build_tool == RATTLER_BUILD:
        assert metadata.meta["requirements"]["host"] == ["python ${{ python_min }}.*"]
    else:
        assert metadata.meta["requirements"]["host"] == ["python 2.7"]

    assert isinstance(metadata, expected_metadata_type)


def test_get_feedstock_name_from_metadata(noarch_recipe):
    feedstock_dir = noarch_recipe[0]
    metadata = _get_metadata_from_feedstock_dir(feedstock_dir, noarch_recipe[1])

    feedstock_name = get_feedstock_name_from_meta(metadata)

    assert feedstock_name == "python-noarch-test"


def test_get_feedstock_name_from_rattler_metadata(
    v1_noarch_recipe_with_context,
):
    feedstock_dir = v1_noarch_recipe_with_context[0]
    metadata = _get_metadata_from_feedstock_dir(
        feedstock_dir, v1_noarch_recipe_with_context[1]
    )

    feedstock_name = get_feedstock_name_from_meta(metadata)

    assert feedstock_name == "python-noarch-test-from-context"


def test_get_feedstock_name_from_rattler_metadata_multiple_outputs(
    v1_recipe_with_multiple_outputs,
):
    feedstock_dir = v1_recipe_with_multiple_outputs[0]
    metadata = _get_metadata_from_feedstock_dir(
        feedstock_dir, v1_recipe_with_multiple_outputs[1]
    )

    feedstock_name = get_feedstock_name_from_meta(metadata)

    assert feedstock_name == "mamba-split"


@pytest.mark.parametrize(
    "restrict,linux_value,linux_or_win_value",
    [
        ({}, True, True),
        ({"os": "linux"}, True, True),
        ({"os": "win"}, None, True),
        ({"os": "osx"}, None, None),
        ({"platform": "linux_64"}, True, True),
        ({"provider": "azure"}, True, True),
        ({"provider": "azure", "os": "linux"}, True, True),
        ({"provider": "azure", "os": "win"}, None, True),
        ({"provider": "azure", "os": "osx"}, None, None),
    ],
)
def test_conditional_value_any_matches(
    restrict: dict[str, Union[str, list[str]]],
    linux_value: bool,
    linux_or_win_value: bool,
) -> None:
    # value passed directly is always used
    assert conditional_value_any_matches(True, **restrict) is True
    assert conditional_value_any_matches(False, **restrict) is False

    # no value
    assert conditional_value_any_matches(None, **restrict) is None
    assert conditional_value_any_matches([], **restrict) is None

    # corner case: a value with no conditions
    assert conditional_value_any_matches([{"value": True}], **restrict) is True
    assert conditional_value_any_matches([{"value": False}], **restrict) is False

    # corner case 2: final value with no conditions
    assert (
        conditional_value_any_matches(
            [
                {"os": "linux", "value": False},
                {"provider": "azure", "value": False},
                {"value": True},
            ],
            **restrict,
        )
        is True
    )
    assert (
        conditional_value_any_matches(
            [
                {"os": "linux", "value": True},
                {"provider": "azure", "value": True},
                {"value": False},
            ],
            **restrict,
        )
        is False
    )

    assert (
        conditional_value_any_matches(
            [
                {"os": "linux", "value": True},
            ],
            **restrict,
        )
        is linux_value
    )
    assert (
        conditional_value_any_matches(
            [
                {"os": ["linux", "win"], "value": True},
            ],
            **restrict,
        )
        is linux_or_win_value
    )
