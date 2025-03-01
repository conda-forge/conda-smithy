import json

from conda_smithy.schema import ConfigModel
from conda_smithy.validate_schema import (
    CONDA_FORGE_YAML_SCHEMA_FILE,
    validate_json_schema,
)


def test_schema_up_to_date():
    model = ConfigModel()

    json_blob_from_model = (
        json.dumps(model.model_json_schema(), indent=2) + "\n"
    )
    assert CONDA_FORGE_YAML_SCHEMA_FILE.exists(), (
        "The config schema file does not exist. "
        "Run `python -m conda_smithy.schema` to generate it."
    )
    json_blob_from_code = CONDA_FORGE_YAML_SCHEMA_FILE.read_text(
        encoding="utf-8"
    )
    assert json.loads(json_blob_from_model) == json.loads(
        json_blob_from_code
    ), (
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
