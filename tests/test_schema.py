import json
import os
import tempfile
import textwrap
from pathlib import Path

import pytest

from conda_smithy.schema import ConfigModel
from conda_smithy.utils import get_yaml
from conda_smithy.validate_schema import (
    CONDA_FORGE_YAML_SCHEMA_FILE,
    validate_json_schema,
)


def test_schema_up_to_date():
    model = ConfigModel()

    json_blob_from_model = json.dumps(model.model_json_schema(), indent=2) + "\n"
    assert CONDA_FORGE_YAML_SCHEMA_FILE.exists(), (
        "The config schema file does not exist. "
        "Run `python -m conda_smithy.schema` to generate it."
    )
    json_blob_from_code = CONDA_FORGE_YAML_SCHEMA_FILE.read_text(encoding="utf-8")
    assert json.loads(json_blob_from_model) == json.loads(json_blob_from_code), (
        "The config schema file is out of date. "
        "Run `python -m conda_smithy.schema` to regenerate it."
    )


def test_schema_validate_json_schema_with_bot():
    cfyaml = {
        "bot": {
            "bad_key_foo_bar_bad": False,
        }
    }

    lints, hints = validate_json_schema(cfyaml)
    assert any("bad_key_foo_bar_bad" in str(lnt) for lnt in lints)
    assert hints == []

    cfyaml = {
        "bot": {
            "automerge": True,
        }
    }
    lints, hints = validate_json_schema(cfyaml)
    assert lints == []
    assert hints == []


def test_schema_no_empty_properties_for_bot():
    """
    If a property references a remote schema with $ref, it should NOT have a properties key.
    This is because some JSON schema validators (VSCode) will fail the validation if a property
    is not in the properties object in this case.
    """
    with (
        Path(__file__)
        .parents[1]
        .joinpath("conda_smithy/data/conda-forge.json")
        .open("r") as f
    ):
        schema = json.load(f)

    assert "properties" not in schema["properties"]["bot"]
    assert schema["properties"]["bot"]["$ref"].startswith("https://")


def test_schema_validate_json_schema_with_bot_uri_override(tmp_path):

    schema_pth = tmp_path / "bot_schema.json"
    with open(schema_pth, "w", encoding="utf-8") as fh:
        fh.write(
            r"""{
  "$defs": {
    "BotConfigAutoMergeChoice": {
      "enum": [
        "version",
        "migration"
      ],
      "title": "BotConfigAutoMergeChoice",
      "type": "string"
    },
    "BotConfigInspectionChoice": {
      "enum": [
        "hint",
        "hint-all",
        "hint-source",
        "hint-grayskull",
        "update-all",
        "update-source",
        "update-grayskull",
        "disabled"
      ],
      "title": "BotConfigInspectionChoice",
      "type": "string"
    },
    "BotConfigVersionUpdates": {
      "additionalProperties": false,
      "description": "This dictates the behavior of the conda-forge auto-tick bot for version\nupdates",
      "properties": {
        "random_fraction_to_keep": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Fraction of versions to keep for frequently updated packages",
          "title": "Random Fraction To Keep"
        },
        "exclude": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": [],
          "description": "List of versions to exclude. Make sure branch names are `str` by quoting the value.",
          "title": "Exclude"
        },
        "sources": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/BotConfigVersionUpdatesSourcesChoice"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of sources to find new versions (i.e. the strings like 1.2.3) for the package.\nThe following sources are available:\n- `cran`: Update from CRAN\n- `github`: Update from the GitHub releases RSS feed (includes pre-releases)\n- `githubreleases`: Get the latest version by following the redirect of\n`https://github.com/{owner}/{repo}/releases/latest` (excludes pre-releases)\n- `incrementalpharawurl`: If this source is run for a specific small selection of feedstocks, it acts like\nthe `rawurl` source but also increments letters in the version string (e.g. 2024a -> 2024b). If the source\nis run for other feedstocks (even if selected manually), it does nothing.\n- `librariesio`: Update from Libraries.io RSS feed\n- `npm`: Update from the npm registry\n- `nvidia`: Update from the NVIDIA download page\n- `pypi`: Update from the PyPI registry\n- `rawurl`: Update from a raw URL by trying to bump the version number in different ways and\nchecking if the URL exists (e.g. 1.2.3 -> 1.2.4, 1.3.0, 2.0.0, etc.)\n- `rosdistro`: Update from a ROS distribution\nCommon issues:\n- If you are using a GitHub-based source in your recipe and the bot issues PRs for pre-releases, restrict\nthe sources to `githubreleases` to avoid pre-releases.\n- If you use source tarballs that are uploaded manually by the maintainers a significant time after a\nGitHub release, you may want to restrict the sources to `rawurl` to avoid the bot attempting to update\nthe recipe before the tarball is uploaded.",
          "title": "Sources"
        },
        "skip": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Skip automatic version updates. Useful in cases where the source project's version numbers don't conform to PEP440.",
          "title": "Skip"
        }
      },
      "title": "BotConfigVersionUpdates",
      "type": "object"
    },
    "BotConfigVersionUpdatesSourcesChoice": {
      "enum": [
        "cran",
        "github",
        "githubreleases",
        "incrementalpharawurl",
        "librariesio",
        "npm",
        "nvidia",
        "pypi",
        "rawurl",
        "rosdistro"
      ],
      "title": "BotConfigVersionUpdatesSourcesChoice",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "description": "This dictates the behavior of the conda-forge auto-tick bot which issues\nautomatic version updates/migrations for feedstocks.",
  "properties": {
    "check_solvable": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": true,
      "description": "Open PRs only if resulting environment is solvable.",
      "title": "Check Solvable"
    },
    "inspection": {
      "anyOf": [
        {
          "$ref": "#/$defs/BotConfigInspectionChoice"
        },
        {
          "type": "null"
        }
      ],
      "default": "hint",
      "description": "Method for generating hints or updating recipe"
    },
    "abi_migration_branches": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": [],
      "description": "List of branches for additional bot migration PRs. Make sure branch names are `str` by quoting the value.",
      "title": "Abi Migration Branches"
    },
    "run_deps_from_wheel": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Update run dependencies from the pip wheel",
      "title": "Run Deps From Wheel"
    },
    "version_updates": {
      "anyOf": [
        {
          "$ref": "#/$defs/BotConfigVersionUpdates"
        },
        {
          "type": "null"
        }
      ],
      "description": "Bot config for version update PRs"
    },
    "update_static_libs": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Update packages in `host` that are used for static linking. For bot to issue update PRs, you must have both an abstract specification of the library (e.g., `llvmdev 15.0.*`) and a concrete specification (e.g., `llvmdev 15.0.7 *_5`). The bot will find the latest package that satisfies the abstract specification and update the concrete specification to this latest package.",
      "title": "Update Static Libs"
    }
  },
  "title": "BotConfig",
  "type": "object"
}
"""
        )
    assert schema_pth.exists(), "The schema file was not created."
    old_val = os.environ.get("CONDA_SMITHY_BOT_SCHEMA_URI")
    try:
        os.environ["CONDA_SMITHY_BOT_SCHEMA_URI"] = "file://" + str(schema_pth)

        cfyaml = {
            "bot": {
                "automerge": True,
            }
        }
        lints, hints = validate_json_schema(cfyaml)
        assert any("automerge" in str(lnt) for lnt in lints)
        assert hints == []

        cfyaml = {
            "bot": {
                "inspection": "hint-all",
                "version_updates": {
                    "random_fraction_to_keep": 0.02,
                },
            }
        }
        lints, hints = validate_json_schema(cfyaml)
        assert lints == []
        assert hints == []

    finally:
        if old_val:
            os.environ["CONDA_SMITHY_BOT_SCHEMA_URI"] = old_val
        else:
            del os.environ["CONDA_SMITHY_BOT_SCHEMA_URI"]


@pytest.mark.xfail(
    reason=(
        "rattler-build-conda-compat makes global modifications to ruamel.yaml"
        " - see https://github.com/prefix-dev/rattler-build-conda-compat/issues/88"
    ),
)
def test_schema_with_rattler_build_conda_compat():
    from rattler_build_conda_compat.yaml import _yaml_object

    _yaml_object()

    with tempfile.TemporaryDirectory() as tmpdir:
        pth = os.path.join(tmpdir, "conda-forge.yml")
        with open(pth, "w") as fp:
            fp.write(
                textwrap.dedent(
                    """\
                bot:
                version_updates:
                    random_fracvtion_to_keep: 0.02
                """
                )
            )
        with open(pth) as fp:
            cfyaml = get_yaml().load(fp)

        lints, hints = validate_json_schema(cfyaml)
        assert lints == []
        assert hints == []
