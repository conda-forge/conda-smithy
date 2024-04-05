import os
import sys
import tempfile
import warnings
from glob import glob
from pathlib import Path
from typing import (
    Optional,
    Dict,
    Iterable,
    Tuple,
    List,
    TypeVar,
    Mapping,
    Sequence,
)

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
    # used for deprecated module members
    if name == "str_type":
        warnings.warn(
            "str_type is deprecated and will be removed in v4, use builtin str instead",
            DeprecationWarning,
        )
        return str
    if name == "FIELDS":
        warnings.warn(
            "FIELDS is deprecated and will be removed in v4, use linters_meta_yaml.FIELDS instead",
            DeprecationWarning,
        )
        return linters_meta_yaml.FIELDS
    if name == "EXPECTED_SECTION_ORDER":
        warnings.warn(
            "EXPECTED_SECTION_ORDER is deprecated and will be removed in v4, use "
            "the order of the linters_meta_yaml.Section enum instead.",
            DeprecationWarning,
        )
        return [str(section) for section in linters_meta_yaml.Section]
    if name == "REQUIREMENTS_ORDER":
        warnings.warn(
            "REQUIREMENTS_ORDER is deprecated and will be removed in v4, use "
            "the order of the linters_meta_yaml.RequirementsSubsection enum instead.",
            DeprecationWarning,
        )
        return [
            str(subsection)
            for subsection in linters_meta_yaml.RequirementsSubsection
        ]
    if name == "TEST_KEYS":
        warnings.warn(
            "TEST_KEYS is deprecated and will be removed in v4, use "
            "linters_meta_yaml.TEST_KEYS instead.",
            DeprecationWarning,
        )
        return linters_meta_yaml.TEST_KEYS
    if name == "TEST_FILES":
        warnings.warn(
            "TEST_FILES is deprecated and will be removed in v4, use "
            "linters_meta_yaml.TEST_FILES instead.",
            DeprecationWarning,
        )
        return linters_meta_yaml.TEST_FILES
    if name == "NEEDED_FAMILIES":
        warnings.warn(
            "NEEDED_FAMILIES is deprecated and will be removed in v4, use "
            "linters_meta_yaml.FAMILIES_NEEDING_LICENSE_FILE instead.",
            DeprecationWarning,
        )
        return linters_meta_yaml.FAMILIES_NEEDING_LICENSE_FILE
    if name == "sel_pat":
        warnings.warn(
            "sel_pat is deprecated and will be removed in v4.",
            DeprecationWarning,
        )
        return linters_meta_yaml._SELECTOR_PATTERN
    if name == "jinja_pat":
        warnings.warn(
            "jinja_pat is deprecated and will be removed in v4.",
            DeprecationWarning,
        )
        return linters_meta_yaml._JINJA_PATTERN
    if name == "JINJA_VAR_PAT":
        warnings.warn(
            "JINJA_VAR_PAT is deprecated and will be removed in v4.",
            DeprecationWarning,
        )
        return linters_meta_yaml._JINJA_VARIABLE_PATTERN
    raise AttributeError(f"module {__name__} has no attribute {name}")


def get_section(parent: dict, name: str, lints: List[str]):
    warnings.warn(
        "get_section is deprecated and will be removed in v4.",
        DeprecationWarning,
    )
    # note: this duplicates code from linters_meta_yaml.get_dict_section_or_subsection but should be removed anyway
    if name == "source":
        return get_list_section(parent, name, lints, allow_single=True)
    elif name == "outputs":
        return get_list_section(parent, name, lints)

    section = parent.get(name, {})
    if not isinstance(section, Mapping):
        lints.append(
            'The "{}" section was expected to be a dictionary, but '
            "got a {}.".format(name, type(section).__name__)
        )
        section = {}
    return section


def get_list_section(
    parent: dict, name: str, lints: List[str], allow_single: bool = False
):
    warnings.warn(
        "get_list_section is deprecated and will be removed in v4.",
        DeprecationWarning,
    )
    # note: this duplicates code from linters_meta_yaml._get_list_section_internal but should be removed anyway
    section = parent.get(name, [])
    if allow_single and isinstance(section, Mapping):
        return [section]
    if isinstance(section, Sequence) and not isinstance(section, str):
        return section
    msg = 'The "{}" section was expected to be a {}list, but got a {}.{}.'.format(
        name,
        "dictionary or a " if allow_single else "",
        type(section).__module__,
        type(section).__name__,
    )
    lints.append(msg)
    return [{}]


def lint_section_order(major_sections: Iterable[str], lints: List[str]):
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


def lint_about_contents(about_section: dict, lints: List[str]):
    warnings.warn(
        "lint_recipe.lint_about_contents is deprecated and will be removed in v4, use"
        "linters_meta_yaml.lint_about_contents instead.",
        DeprecationWarning,
    )

    meta_yaml = {"about": about_section}
    results = linters_meta_yaml.lint_about_contents(
        meta_yaml, MetaYamlLintExtras()
    )

    lints.extend(results.lints)


def find_local_config_file(recipe_dir: str, filename: str) -> Optional[str]:
    warnings.warn(
        "find_local_config_file is deprecated and will be removed in v4.",
        DeprecationWarning,
    )
    # this duplicates the logic from config_file_helpers.read_local_config_file but should be removed anyway
    # support
    # 1. feedstocks
    # 2. staged-recipes with custom conda-forge.yaml in recipe
    # 3. staged-recipes
    found_filename = (
        glob(os.path.join(recipe_dir, filename))
        or glob(
            os.path.join(recipe_dir, "..", filename),
        )
        or glob(
            os.path.join(recipe_dir, "..", "..", filename),
        )
    )

    return found_filename[0] if found_filename else None


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


def is_selector_line(
    line: str,
    allow_platforms: bool = False,
    allow_keys: Optional[AbstractSet] = None,
):
    warnings.warn(
        "is_selector_line is deprecated and will be removed in v4, "
        "use linters_meta_yaml.is_selector_line instead.",
        DeprecationWarning,
    )
    return linters_meta_yaml.is_selector_line(
        line, allow_platforms, allow_keys
    )


def is_jinja_line(line: str) -> bool:
    warnings.warn(
        "is_jinja_line is deprecated and will be removed in v4. "
        "Use linters_meta_yaml.is_jinja_line instead.",
        DeprecationWarning,
    )
    return linters_meta_yaml.is_jinja_line(line)


def selector_lines(lines):
    warnings.warn(
        "selector_lines is deprecated and will be removed in v4. "
        "Use linters_meta_yaml.selector_lines instead.",
        DeprecationWarning,
    )
    return linters_meta_yaml.selector_lines(lines)


def jinja_lines(lines):
    warnings.warn(
        "jinja_lines is deprecated and will be removed in v4. "
        "Use linters_meta_yaml.jinja_lines instead.",
        DeprecationWarning,
    )
    return linters_meta_yaml.jinja_lines(lines)


def main(
    recipe_dir: str, conda_forge: bool = False, return_hints: bool = False
):
    recipe_dir = os.path.abspath(recipe_dir)
    recipe_meta = os.path.join(recipe_dir, "meta.yaml")
    if not os.path.exists(recipe_dir):
        raise IOError("Feedstock has no recipe/meta.yaml.")

    with open(recipe_meta, "r") as fh:
        content = render_meta_yaml("".join(fh))
        meta = get_yaml().load(content)

    if not isinstance(meta, dict):
        raise ValueError("The meta.yaml file does not represent a dictionary.")

    results = lint_meta_yaml(meta, Path(recipe_dir), conda_forge)
    forge_yaml_results = lint_forge_yaml(recipe_dir=Path(recipe_dir))

    results += forge_yaml_results

    if return_hints:
        return results.lints, results.hints
    else:
        return results.lints


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
