import os

import jsonschema
import yaml
import yamllint.linter
import yamllint.config

from .configure_feedstock import conda_forge_file, _read_forge_config

conda_forge_schema_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "schema", "conda-forge.schema.yml")
)

with open(conda_forge_schema_path, encoding="utf-8") as _sfp:
    conda_forge_schema = yaml.safe_load(_sfp)

conda_forge_validator = jsonschema.Draft7Validator(conda_forge_schema)

yamllint_config = yamllint.config.YamlLintConfig(
    """
extends: default
rules:
    # the 0th will be taken
    document-start: disable
    # tokens are very long
    line-length: disable
    indentation: disable
"""
)


def lintify(forge_dir, forge_yml=None, raw=False):
    with open(
        os.path.join(forge_dir, conda_forge_file), encoding="utf8"
    ) as _cptr:
        syntax_results = list(
            yamllint.linter.run(_cptr, yamllint_config),
        )

    if not raw:
        syntax_results = [f"{result}" for result in syntax_results]

    config, file_config = _read_forge_config(forge_dir, forge_yml)

    schema_results = list(conda_forge_validator.iter_errors(config))
    if not raw:
        schema_results = [
            f"""#{"/".join(["", *result.path])}: {result.message}"""
            for result in schema_results
        ]

    return [*syntax_results, *schema_results]


def main(forge_dir):
    forge_dir = os.path.abspath(forge_dir)
    forge_config = os.path.join(forge_dir, conda_forge_file)
    if not os.path.exists(forge_dir):
        raise IOError(f"Feedstock has no `{conda_forge_file}`.")

    return lintify(forge_dir)
