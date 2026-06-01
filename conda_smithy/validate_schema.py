import json
import os
from pathlib import Path

import requests
from jsonschema import Draft202012Validator, validators
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONDA_FORGE_YAML_DEFAULTS_FILE = (
    Path(__file__).resolve().parent / "data" / "conda-forge.yml"
)

CONDA_FORGE_YAML_SCHEMA_FILE = (
    Path(__file__).resolve().parent / "data" / "conda-forge.json"
)


class DeprecatedValidator:
    def __init__(self):
        self.hints = []

    def __call__(self, validator, value, instance, schema):
        if value and instance is not None:
            self.hints.append(
                f"'{schema['title']}' is deprecated.\n{schema['description']}"
            )


def get_validator_class(deprecated_validator):
    all_validators = dict(Draft202012Validator.VALIDATORS)
    all_validators["deprecated"] = deprecated_validator

    return validators.create(
        meta_schema=Draft202012Validator.META_SCHEMA, validators=all_validators
    )


def validate_json_schema(
    config, schema_file: str = None
) -> tuple[list[ValidationError], list[ValidationError]]:
    # Validate the merged configuration against a JSON schema
    if not schema_file:
        schema_file = CONDA_FORGE_YAML_SCHEMA_FILE

    with open(schema_file, encoding="utf-8") as fh:
        _json_schema = json.loads(fh.read())

    def _get_json_schema(uri: str):
        if uri.startswith("file://"):
            assert Path(uri[7:]).is_file()
            val = json.loads(Path(uri[7:]).read_text(encoding="utf-8"))
        else:
            response = requests.get(uri)
            response.raise_for_status()
            val = response.json()

        return Resource.from_contents(val, default_specification=DRAFT202012)

    # allow the URI to be set dynamically
    if "CONDA_SMITHY_BOT_SCHEMA_URI" in os.environ:
        _json_schema["properties"]["bot"]["$ref"] = os.environ[
            "CONDA_SMITHY_BOT_SCHEMA_URI"
        ]

    deprecated_validator = DeprecatedValidator()
    validator = get_validator_class(deprecated_validator)(
        _json_schema, registry=Registry(retrieve=_get_json_schema)
    )
    return list(validator.iter_errors(config)), deprecated_validator.hints
