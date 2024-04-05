import os
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Optional, Dict, Iterable, Tuple, List, TypeVar

from conda_smithy import linters_meta_yaml
from conda_smithy.config_file_helpers import (
    read_local_config_file,
    ConfigFileName,
    ConfigFileMustBeDictError,
    MultipleConfigFilesError,
)
from conda_smithy.linters_forge_yml import (
    FORGE_YAML_LINTERS,
)
from conda_smithy.linters_meta_yaml import (
    MetaYamlLintExtras,
)
from conda_smithy.linting_utils import LintsHints, Linter, AutoLintException
from .utils import render_meta_yaml, get_yaml

T = TypeVar("T")


def __getattr__(name):
    if name == "str_type":
        warnings.warn(
            "str_type is deprecated and will be removed in v4, use builtin str instead",
            DeprecationWarning,
        )
        return str
    raise AttributeError(f"module {__name__} has no attribute {name}")


def lint_section_order(major_sections: Iterable[list], lints: List[str]):
    warnings.warn(
        "lint_recipe.lint_section_order is deprecated and will be removed in v4, use"
        "linters_meta_yaml.lint_section_order instead (changed signature).",
        DeprecationWarning,
    )
    meta_yaml = {section: "dummy_value" for section in major_sections}

    result = linters_meta_yaml.lint_section_order(
        meta_yaml, MetaYamlLintExtras()
    )

    lints.extend(result.lints)


def _lint(
    contents: Dict, linters: Iterable[Linter[T]], lint_extras: T = None
) -> LintsHints:
    """
    Lint the contents of a file. Automatically catch AutoLintExceptions and convert them to lints.
    :param contents: the contents of the file to lint
    :param linters: an iterable of linters to apply to the contents
    :param lint_extras: static extra data to pass to the linters
    :returns: a LintsHints object, containing lints and hints
    """
    results = LintsHints()

    for linter in linters:
        try:
            results += linter(contents, lint_extras)
        except AutoLintException as e:
            results.append_lint(str(e))

    return results


def lint_forge_yaml(recipe_dir: Path) -> LintsHints:
    """
    Lint the conda-forge.yml file, relative to the recipe_dir.
    :returns: a LintsHints object, containing lints and hints
    """
    additional_lints = LintsHints()
    yaml: dict

    try:
        yaml = read_local_config_file(
            recipe_dir, ConfigFileName.CONDA_FORGE_YML
        )
    except (ConfigFileMustBeDictError, MultipleConfigFilesError) as e:
        return LintsHints.lint(str(e))
    except FileNotFoundError:
        additional_lints.append_hint(
            "No conda-forge.yml file found. This is treated as an empty config mapping."
        )
        yaml = {}
    return _lint(yaml, FORGE_YAML_LINTERS) + additional_lints


def lintify_forge_yaml(
    recipe_dir: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    warnings.warn(
        "lintify_forge_yaml is deprecated and will be removed in v4, use lint_forge_yaml instead. "
        "Make sure to pass a Path object and expect a LintsHints object as return value. "
        "recipe_dir becomes a required argument.",
        DeprecationWarning,
    )

    lint_result: LintsHints

    if recipe_dir:
        lint_result = lint_forge_yaml(Path(recipe_dir))
    else:
        with tempfile.TemporaryDirectory() as tmp_dirname:
            tmp_dir = Path(tmp_dirname)
            child_dir = tmp_dir / "child"
            child_dir.mkdir()

            with open(tmp_dir / "conda-forge.yml", "w") as f:
                f.write("{}")

            lint_result = lint_forge_yaml(child_dir)

    return lint_result.lints, lint_result.hints


def lint_meta_yaml(
    meta_yaml: dict, recipe_dir: Optional[Path], is_conda_forge: bool = False
) -> LintsHints:
    """
    Lint the meta.yaml file.
    :param meta_yaml: the parsed meta.yaml file to lint
    :param recipe_dir: the directory containing the recipe (optional, this allows additional linting)
    :param is_conda_forge: whether the recipe is a conda-forge recipe (optional, this enables additional linting)
    :returns: a LintsHints object, containing lints and hints
    """
    extras = MetaYamlLintExtras(recipe_dir, is_conda_forge)
    return _lint(meta_yaml, linters_meta_yaml.META_YAML_LINTERS, extras)


def lintify_meta_yaml(
    meta: dict, recipe_dir: Optional[str] = None, conda_forge: bool = False
) -> Tuple[List[str], List[str]]:
    """
    DEPRECATED: Lint the meta.yaml file, relative to the recipe_dir.
    :returns: a tuple (lints, hints)
    """

    warnings.warn(
        "lintify_meta_yaml is deprecated and will be removed in v4, use lint_meta_yaml (signature changed) instead. ",
        DeprecationWarning,
    )

    recipe_dir_path = Path(recipe_dir) if recipe_dir else None

    lint_result = lint_meta_yaml(meta, recipe_dir_path, conda_forge)

    return lint_result.lints, lint_result.hints


def main(recipe_dir, conda_forge=False, return_hints=False):
    recipe_dir = os.path.abspath(recipe_dir)
    recipe_meta = os.path.join(recipe_dir, "meta.yaml")
    if not os.path.exists(recipe_dir):
        raise IOError("Feedstock has no recipe/meta.yaml.")

    with open(recipe_meta, "rt") as fh:
        content = render_meta_yaml("".join(fh))
        meta = get_yaml().load(content)

    lints, hints = lintify_meta_yaml(meta, recipe_dir, conda_forge)
    forge_yaml_results = lint_forge_yaml(recipe_dir=Path(recipe_dir))

    lints.extend(forge_yaml_results.lints)
    hints.extend(forge_yaml_results.hints)

    if return_hints:
        return lints, hints
    else:
        return lints


def main_debug():
    # This function is supposed to help debug how the rendered version
    # of the linter bot would look like in GitHub. Taken from
    # https://github.com/conda-forge/conda-forge-webservices/blob/747f75659/conda_forge_webservices/linting.py#L138C1-L146C72
    rel_path = sys.argv[1]
    lints, hints = main(rel_path, False, True)
    messages = []
    if lints:
        all_pass = False
        messages.append(
            "\nFor **{}**:\n\n{}".format(
                rel_path, "\n".join("* {}".format(lint) for lint in lints)
            )
        )
    if hints:
        messages.append(
            "\nFor **{}**:\n\n{}".format(
                rel_path, "\n".join("* {}".format(hint) for hint in hints)
            )
        )

    print(*messages, sep="\n")


if __name__ == "__main__":
    main_debug()
