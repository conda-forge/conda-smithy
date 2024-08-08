import json
import os
import sys
from collections.abc import Mapping
from glob import glob
from inspect import cleandoc
from pathlib import Path
from textwrap import indent
from typing import List, Tuple

import github
import jsonschema
import requests

from conda_smithy.linter import conda_recipe_v1_linter
from conda_smithy.linter.hints import (
    hint_check_spdx,
    hint_pip_usage,
    hint_shellcheck_usage,
    hint_suggest_noarch,
)
from conda_smithy.linter.lints import (
    lint_about_contents,
    lint_build_section_should_be_before_run,
    lint_build_section_should_have_a_number,
    lint_check_usage_of_whls,
    lint_go_licenses_are_bundled,
    lint_jinja_var_references,
    lint_jinja_variables_definitions,
    lint_legacy_usage_of_compilers,
    lint_license_cannot_be_unknown,
    lint_license_family_should_be_valid,
    lint_license_should_not_have_license,
    lint_noarch,
    lint_noarch_and_runtime_dependencies,
    lint_non_noarch_builds,
    lint_package_version,
    lint_pin_subpackages,
    lint_recipe_have_tests,
    lint_recipe_maintainers,
    lint_recipe_name,
    lint_recipe_v1_noarch_and_runtime_dependencies,
    lint_require_lower_bound_on_python_version,
    lint_rust_licenses_are_bundled,
    lint_section_order,
    lint_selectors_should_be_in_tidy_form,
    lint_should_be_empty_line,
    lint_single_space_in_pinned_requirements,
    lint_sources_should_have_hash,
    lint_stdlib,
    lint_subheaders,
    lint_usage_of_legacy_patterns,
)
from conda_smithy.linter.utils import (
    CONDA_BUILD_TOOL,
    EXPECTED_SECTION_ORDER,
    RATTLER_BUILD_TOOL,
    find_local_config_file,
    get_section,
)

if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from conda_build.metadata import (
    ensure_valid_license_family,
)
from rattler_build_conda_compat import loader as rattler_loader

from conda_smithy.configure_feedstock import _read_forge_config
from conda_smithy.utils import get_yaml, render_meta_yaml
from conda_smithy.validate_schema import validate_json_schema

NEEDED_FAMILIES = ["gpl", "bsd", "mit", "apache", "psf"]


def lintify_forge_yaml(recipe_dir=None) -> (list, list):
    if recipe_dir:
        forge_yaml_filename = (
            glob(os.path.join(recipe_dir, "..", "conda-forge.yml"))
            or glob(
                os.path.join(recipe_dir, "conda-forge.yml"),
            )
            or glob(
                os.path.join(recipe_dir, "..", "..", "conda-forge.yml"),
            )
        )
        if forge_yaml_filename:
            with open(forge_yaml_filename[0]) as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        forge_yaml = {}

    # This is where we validate against the jsonschema and execute our custom validators.
    return validate_json_schema(forge_yaml)


def lintify_meta_yaml(
    meta,
    recipe_dir=None,
    conda_forge=False,
    recipe_version: int = 0,
) -> Tuple[List[str], List[str]]:
    lints = []
    hints = []
    major_sections = list(meta.keys())

    # If the recipe_dir exists (no guarantee within this function) , we can
    # find the meta.yaml within it.
    recipe_name = "meta.yaml" if recipe_version == 0 else "recipe.yaml"
    recipe_fname = os.path.join(recipe_dir or "", recipe_name)

    sources_section = get_section(meta, "source", lints, recipe_version)
    build_section = get_section(meta, "build", lints, recipe_version)
    requirements_section = get_section(
        meta, "requirements", lints, recipe_version
    )
    build_requirements = requirements_section.get("build", [])
    run_reqs = requirements_section.get("run", [])
    if recipe_version == 1:
        test_section = get_section(meta, "tests", lints, recipe_version)
    else:
        test_section = get_section(meta, "test", lints, recipe_version)
    about_section = get_section(meta, "about", lints, recipe_version)
    extra_section = get_section(meta, "extra", lints, recipe_version)
    package_section = get_section(meta, "package", lints, recipe_version)
    outputs_section = get_section(meta, "outputs", lints, recipe_version)

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    is_staged_recipes = recipe_dirname != "recipe"

    # 0: Top level keys should be expected
    unexpected_sections = []
    if recipe_version == 0:
        expected_keys = EXPECTED_SECTION_ORDER
    else:
        expected_keys = (
            conda_recipe_v1_linter.EXPECTED_SINGLE_OUTPUT_SECTION_ORDER
            + conda_recipe_v1_linter.EXPECTED_MULTIPLE_OUTPUT_SECTION_ORDER
        )

    for section in major_sections:
        if section not in expected_keys:
            lints.append(f"The top level meta key {section} is unexpected")
            unexpected_sections.append(section)

    for section in unexpected_sections:
        major_sections.remove(section)

    # 1: Top level meta.yaml keys should have a specific order.
    lint_section_order(major_sections, lints, recipe_version)

    # 2: The about section should have a home, license and summary.
    lint_about_contents(about_section, lints, recipe_version)

    # 3a: The recipe should have some maintainers.
    # 3b: Maintainers should be a list
    lint_recipe_maintainers(extra_section, lints)

    # 4: The recipe should have some tests.
    lint_recipe_have_tests(
        recipe_dir,
        test_section,
        outputs_section,
        lints,
        hints,
        recipe_version,
    )

    # 5: License cannot be 'unknown.'
    lint_license_cannot_be_unknown(about_section, lints)

    # 6: Selectors should be in a tidy form.
    if recipe_version == 0:
        # v1 does not have selectors in comments form
        lint_selectors_should_be_in_tidy_form(recipe_fname, lints, hints)

    # 7: The build section should have a build number.
    lint_build_section_should_have_a_number(build_section, lints)

    # 8: The build section should be before the run section in requirements.
    lint_build_section_should_be_before_run(requirements_section, lints)

    # 9: Files downloaded should have a hash.
    if recipe_version == 1:
        lint_sources_should_have_hash(sources_section, lints)
    elif recipe_version == 2:
        conda_recipe_v2_linter.lint_sources(sources_section, lints)

    # 10: License should not include the word 'license'.
    lint_license_should_not_have_license(about_section, lints)

    # 11: There should be one empty line at the end of the file.
    lint_should_be_empty_line(recipe_fname, lints)

    # 12: License family must be valid (conda-build checks for that)
    # we skip it for v1 builds as it will validate it
    # See more: https://prefix-dev.github.io/rattler-build/latest/reference/recipe_file/#about-section
    if recipe_version == 0:
        try:
            ensure_valid_license_family(meta)
        except RuntimeError as e:
            lints.append(str(e))

    # 12a: License family must be valid (conda-build checks for that)
    license = about_section.get("license", "").lower()
    lint_license_family_should_be_valid(
        about_section, license, NEEDED_FAMILIES, lints, recipe_version
    )

    # 13: Check that the recipe name is valid
    if recipe_version == 1:
        conda_recipe_v1_linter.lint_recipe_name(meta, lints)
    else:
        lint_recipe_name(
            package_section,
            lints,
        )

    # 14: Run conda-forge specific lints
    if conda_forge:
        run_conda_forge_specific(
            meta, recipe_dir, lints, hints, recipe_version=recipe_version
        )

    # 15: Check if we are using legacy patterns
    lint_usage_of_legacy_patterns(requirements_section, lints)

    # 16: Subheaders should be in the allowed subheadings
    if recipe_version == 0:
        lint_subheaders(major_sections, meta, lints)

    # 17: Validate noarch
    noarch_value = build_section.get("noarch")
    lint_noarch(noarch_value, lints)

    conda_build_config_filename = None
    if recipe_dir:
        cbc_file = "conda_build_config.yaml"
        if recipe_version == 1:
            cbc_file = "variants.yaml"

        conda_build_config_filename = find_local_config_file(
            recipe_dir, cbc_file
        )

        if conda_build_config_filename:
            with open(conda_build_config_filename) as fh:
                conda_build_config_keys = set(get_yaml().load(fh).keys())
        else:
            conda_build_config_keys = set()

        forge_yaml_filename = find_local_config_file(
            recipe_dir, "conda-forge.yml"
        )

        if forge_yaml_filename:
            with open(forge_yaml_filename) as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        conda_build_config_keys = set()
        forge_yaml = {}

    # 18: noarch doesn't work with selectors for runtime dependencies
    noarch_platforms = len(forge_yaml.get("noarch_platforms", [])) > 1
    if recipe_version == 1:
        raw_requirements_section = meta.get("requirements", {})
        lint_recipe_v1_noarch_and_runtime_dependencies(
            noarch_value,
            raw_requirements_section,
            build_section,
            noarch_platforms,
            lints,
        )
    else:
        lint_noarch_and_runtime_dependencies(
            noarch_value,
            recipe_fname,
            forge_yaml,
            conda_build_config_keys,
            lints,
        )

    # 19: check version
    if recipe_version == 1:
        conda_recipe_v1_linter.lint_package_version(meta, lints)
    else:
        lint_package_version(package_section, lints)

    # 20: Jinja2 variable definitions should be nice.
    lint_jinja_variables_definitions(recipe_fname, lints)

    # 21: Legacy usage of compilers
    lint_legacy_usage_of_compilers(build_requirements, lints)

    # 22: Single space in pinned requirements
    lint_single_space_in_pinned_requirements(requirements_section, lints)

    # 23: non noarch builds shouldn't use version constraints on python and r-base
    lint_non_noarch_builds(
        requirements_section, outputs_section, noarch_value, lints
    )

    # 24: jinja2 variable references should be {{<one space>var<one space>}}
    lint_jinja_var_references(
        recipe_fname, hints, recipe_version=recipe_version
    )

    # 25: require a lower bound on python version
    lint_require_lower_bound_on_python_version(
        run_reqs, outputs_section, noarch_value, lints
    )

    # 26: pin_subpackage is for subpackages and pin_compatible is for
    # non-subpackages of the recipe. Contact @carterbox for troubleshooting
    # this lint.
    lint_pin_subpackages(
        meta,
        outputs_section,
        package_section,
        lints,
        recipe_version=recipe_version,
    )

    # 27: Check usage of whl files as a source
    lint_check_usage_of_whls(recipe_fname, noarch_value, lints, hints)

    # 28: Check that Rust licenses are bundled.
    lint_rust_licenses_are_bundled(
        build_requirements, lints, recipe_version=recipe_version
    )

    # 29: Check that go licenses are bundled.
    lint_go_licenses_are_bundled(
        build_requirements, lints, recipe_version=recipe_version
    )

    # hints
    # 1: suggest pip
    hint_pip_usage(build_section, hints)

    # 2: suggest python noarch (skip on feedstocks)
    raw_requirements_section = meta.get("requirements", {})
    hint_suggest_noarch(
        noarch_value,
        build_requirements,
        raw_requirements_section,
        is_staged_recipes,
        conda_forge,
        recipe_fname,
        hints,
        recipe_version=recipe_version,
    )

    # 3: suggest fixing all recipe/*.sh shellcheck findings
    hint_shellcheck_usage(recipe_dir, hints)

    # 4: Check for SPDX
    hint_check_spdx(about_section, hints)

    # 5: stdlib-related lints
    lint_stdlib(
        meta,
        requirements_section,
        conda_build_config_filename,
        lints,
        hints,
        recipe_version=recipe_version,
    )

    return lints, hints


def run_conda_forge_specific(
    meta,
    recipe_dir,
    lints,
    hints,
    recipe_version: int = 0,
):
    gh = github.Github(os.environ["GH_TOKEN"])

    # Retrieve sections from meta
    package_section = get_section(
        meta, "package", lints, recipe_version=recipe_version
    )
    extra_section = get_section(
        meta, "extra", lints, recipe_version=recipe_version
    )
    sources_section = get_section(
        meta, "source", lints, recipe_version=recipe_version
    )
    requirements_section = get_section(
        meta, "requirements", lints, recipe_version=recipe_version
    )
    outputs_section = get_section(
        meta, "outputs", lints, recipe_version=recipe_version
    )

    # Fetch list of recipe maintainers
    maintainers = extra_section.get("recipe-maintainers", [])

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    if recipe_version == 1:
        recipe_name = conda_recipe_v1_linter.get_recipe_name(meta)
    else:
        recipe_name = package_section.get("name", "").strip()
    is_staged_recipes = recipe_dirname != "recipe"

    # 1: Check that the recipe does not exist in conda-forge or bioconda
    if is_staged_recipes and recipe_name:
        cf = gh.get_user(os.getenv("GH_ORG", "conda-forge"))

        for name in set(
            [
                recipe_name,
                recipe_name.replace("-", "_"),
                recipe_name.replace("_", "-"),
            ]
        ):
            try:
                if cf.get_repo(f"{name}-feedstock"):
                    existing_recipe_name = name
                    feedstock_exists = True
                    break
                else:
                    feedstock_exists = False
            except github.UnknownObjectException:
                feedstock_exists = False

        if feedstock_exists and existing_recipe_name == recipe_name:
            lints.append("Feedstock with the same name exists in conda-forge.")
        elif feedstock_exists:
            hints.append(
                f"Feedstock with the name {existing_recipe_name} exists in conda-forge. Is it the same as this package ({recipe_name})?"
            )

        bio = gh.get_user("bioconda").get_repo("bioconda-recipes")
        try:
            bio.get_dir_contents(f"recipes/{recipe_name}")
        except github.UnknownObjectException:
            pass
        else:
            hints.append(
                "Recipe with the same name exists in bioconda: "
                "please discuss with @conda-forge/bioconda-recipes."
            )

        url = None
        if recipe_version == 1:
            for source_url in sources_section:
                if source_url.startswith("https://pypi.io/packages/source/"):
                    url = source_url
        else:
            for source_section in sources_section:
                if str(source_section.get("url")).startswith(
                    "https://pypi.io/packages/source/"
                ):
                    url = source_section["url"]
        if url:
            # get pypi name from  urls like "https://pypi.io/packages/source/b/build/build-0.4.0.tar.gz"
            pypi_name = url.split("/")[6]
            mapping_request = requests.get(
                "https://raw.githubusercontent.com/regro/cf-graph-countyfair/master/mappings/pypi/name_mapping.yaml"
            )
            if mapping_request.status_code == 200:
                mapping_raw_yaml = mapping_request.content
                mapping = get_yaml().load(mapping_raw_yaml)
                for pkg in mapping:
                    if pkg.get("pypi_name", "") == pypi_name:
                        conda_name = pkg["conda_name"]
                        hints.append(
                            f"A conda package with same name ({conda_name}) already exists."
                        )

    # 2: Check that the recipe maintainers exists:
    for maintainer in maintainers:
        if "/" in maintainer:
            # It's a team. Checking for existence is expensive. Skip for now
            continue
        try:
            gh.get_user(maintainer)
        except github.UnknownObjectException:
            lints.append(f'Recipe maintainer "{maintainer}" does not exist')

    # 3: if the recipe dir is inside the example dir
    if recipe_dir is not None and "recipes/example/" in recipe_dir:
        lints.append(
            "Please move the recipe out of the example dir and "
            "into its own dir."
        )

    # 4: Do not delete example recipe
    if is_staged_recipes and recipe_dir is not None:
        for recipe_name in ("meta.yaml", "recipe.yaml"):
            example_fname = os.path.abspath(
                os.path.join(recipe_dir, "..", "example", recipe_name)
            )

            if not os.path.exists(example_fname):
                msg = (
                    "Please do not delete the example recipe found in "
                    f"`recipes/example/{recipe_name}`."
                )

                if msg not in lints:
                    lints.append(msg)

    # 5: Package-specific hints
    # (e.g. do not depend on matplotlib, only matplotlib-base)
    build_reqs = requirements_section.get("build") or []
    host_reqs = requirements_section.get("host") or []
    run_reqs = requirements_section.get("run") or []
    for out in outputs_section:
        if recipe_version == 1:
            output_requirements = rattler_loader.load_all_requirements(out)
            build_reqs += output_requirements.get("build") or []
            host_reqs += output_requirements.get("host") or []
            run_reqs += output_requirements.get("run") or []
        else:
            _req = out.get("requirements") or {}
            if isinstance(_req, Mapping):
                build_reqs += _req.get("build") or []
                host_reqs += _req.get("host") or []
                run_reqs += _req.get("run") or []
            else:
                run_reqs += _req

    hints_toml_url = "https://raw.githubusercontent.com/conda-forge/conda-forge-pinning-feedstock/main/recipe/linter_hints/hints.toml"
    hints_toml_req = requests.get(hints_toml_url)
    if hints_toml_req.status_code != 200:
        # too bad, but not important enough to throw an error;
        # linter will rerun on the next commit anyway
        return
    hints_toml_str = hints_toml_req.content.decode("utf-8")
    specific_hints = tomllib.loads(hints_toml_str)["hints"]

    for rq in build_reqs + host_reqs + run_reqs:
        dep = rq.split(" ")[0].strip()
        if dep in specific_hints and specific_hints[dep] not in hints:
            hints.append(specific_hints[dep])

    # 6: Check if all listed maintainers have commented:
    pr_number = os.environ.get("STAGED_RECIPES_PR_NUMBER")

    if is_staged_recipes and maintainers and pr_number:
        # Get PR details using GitHub API
        current_pr = gh.get_repo("conda-forge/staged-recipes").get_pull(
            int(pr_number)
        )

        # Get PR author, issue comments, and review comments
        pr_author = current_pr.user.login
        issue_comments = current_pr.get_issue_comments()
        review_comments = current_pr.get_reviews()

        # Combine commenters from both issue comments and review comments
        commenters = {comment.user.login for comment in issue_comments}
        commenters.update({review.user.login for review in review_comments})

        # Check if all maintainers have either commented or are the PR author
        non_participating_maintainers = set()
        for maintainer in maintainers:
            if maintainer not in commenters and maintainer != pr_author:
                non_participating_maintainers.add(maintainer)

        # Add a lint message if there are any non-participating maintainers
        if non_participating_maintainers:
            lints.append(
                f"The following maintainers have not yet confirmed that they are willing to be listed here: "
                f"{', '.join(non_participating_maintainers)}. Please ask them to comment on this PR if they are."
            )

    # 7: Ensure that the recipe has some .ci_support files
    if not is_staged_recipes and recipe_dir is not None:
        ci_support_files = glob(
            os.path.join(recipe_dir, "..", ".ci_support", "*.yaml")
        )
        if not ci_support_files:
            lints.append(
                "The feedstock has no `.ci_support` files and thus will not build any packages."
            )


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


def main(
    recipe_dir, conda_forge=False, return_hints=False, feedstock_dir=None
):
    recipe_dir = os.path.abspath(recipe_dir)
    build_tool = CONDA_BUILD_TOOL
    if feedstock_dir:
        feedstock_dir = os.path.abspath(feedstock_dir)
        forge_config = _read_forge_config(feedstock_dir)
        if forge_config.get("conda_build_tool", "") == RATTLER_BUILD_TOOL:
            build_tool = RATTLER_BUILD_TOOL

    if build_tool == RATTLER_BUILD_TOOL:
        recipe_file = os.path.join(recipe_dir, "recipe.yaml")
    else:
        recipe_file = os.path.join(recipe_dir, "meta.yaml")

    if not os.path.exists(recipe_file):
        raise OSError(
            f"Feedstock has no recipe/{os.path.basename(recipe_file)}"
        )

    if build_tool == CONDA_BUILD_TOOL:
        with open(recipe_file) as fh:
            content = render_meta_yaml("".join(fh))
            meta = get_yaml().load(content)
    else:
        meta = get_yaml().load(Path(recipe_file))

    recipe_version = 1 if build_tool == RATTLER_BUILD_TOOL else 0
    results, hints = lintify_meta_yaml(
        meta,
        recipe_dir,
        conda_forge,
        recipe_version=recipe_version,
    )
    validation_errors, validation_hints = lintify_forge_yaml(
        recipe_dir=recipe_dir
    )

    results.extend([_format_validation_msg(err) for err in validation_errors])
    hints.extend([_format_validation_msg(hint) for hint in validation_hints])

    if return_hints:
        return results, hints
    else:
        return results


if __name__ == "__main__":
    # This block is supposed to help debug how the rendered version
    # of the linter bot would look like in Github. Taken from
    # https://github.com/conda-forge/conda-forge-webservices/blob/747f75659/conda_forge_webservices/linting.py#L138C1-L146C72
    rel_path = sys.argv[1]
    lints, hints = main(rel_path, False, True)
    messages = []
    if lints:
        all_pass = False
        messages.append(
            "\nFor **{}**:\n\n{}".format(
                rel_path, "\n".join(f"* {lint}" for lint in lints)
            )
        )
    if hints:
        messages.append(
            "\nFor **{}**:\n\n{}".format(
                rel_path, "\n".join(f"* {hint}" for hint in hints)
            )
        )

    print(*messages, sep="\n")
