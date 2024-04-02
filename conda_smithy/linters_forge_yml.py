import json
from inspect import cleandoc
from textwrap import indent

import jsonschema
from pydantic import BaseModel

from conda_smithy.linting_types import Linter, LintsHints
from conda_smithy.schema import ConfigModel
from conda_smithy.validate_schema import validate_json_schema


def _format_validation_msg(error: jsonschema.ValidationError):
    """Use the data on the validation error to generate improved reporting.

    If available, get the help URL from the first level of the JSON path:

        $(.top_level_key.2nd_level_key)
    """
    help_url = "https://conda-forge.org/docs/maintainer/conda_forge_yml"
    path = error.json_path.split(".")
    descriptionless_schema = {}
    subschema_text = ""

    if error.schema:
        descriptionless_schema = {
            k: v for (k, v) in error.schema.items() if k != "description"
        }

    if len(path) > 1:
        help_url += f"""/#{path[1].split("[")[0].replace("_", "-")}"""
        subschema_text = json.dumps(descriptionless_schema, indent=2)

    return cleandoc(
        f"""
        In conda-forge.yml: [`{error.json_path}`]({help_url}) `=` `{error.instance}`.
{indent(error.message, " " * 12 + "> ")}
            <details>
            <summary>Schema</summary>

            ```json
{indent(subschema_text, " " * 12)}
            ```

            </details>
        """
    )


def lint_validate_json(forge_yaml: dict) -> LintsHints:
    validation_lints, validation_hints = validate_json_schema(forge_yaml)

    lints = [_format_validation_msg(lint) for lint in validation_lints]
    hints = [_format_validation_msg(hint) for hint in validation_hints]

    return LintsHints(lints, hints)


def lint_extra_fields(
    forge_yaml: dict,
) -> LintsHints:
    """
    Identify unexpected keys in the conda-forge.yml file.
    This only works if extra="allow" is set in the Pydantic sub-model where the unexpected key is found.
    """

    config = ConfigModel.model_validate(forge_yaml)
    hints = []

    def _find_extra_fields(model: BaseModel, prefix=""):
        for extra_field in (model.__pydantic_extra__ or {}).keys():
            hints.append(f"Unexpected key {prefix + extra_field}")

        for field, value in model:
            if isinstance(value, BaseModel):
                _find_extra_fields(value, f"{prefix + field}.")

    _find_extra_fields(config)

    return LintsHints(hints=hints)


FORGE_YAML_LINTERS: list[Linter] = [
    lint_validate_json,
    lint_extra_fields,
]
