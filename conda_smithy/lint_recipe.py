import copy
import json
import os
import sys
from collections.abc import Mapping
from functools import lru_cache
from glob import glob
from inspect import cleandoc
from pathlib import Path
from textwrap import indent
from typing import Any, Optional

import github
import github.Auth
import github.Organization
import github.Team
import jsonschema
import requests
from conda_build.metadata import (
    ensure_valid_license_family,
)
from rattler_build_conda_compat import loader as rattler_loader
from ruamel.yaml.constructor import DuplicateKeyError

from conda_smithy.configure_feedstock import _read_forge_config
from conda_smithy.linter import conda_recipe_v1_linter
from conda_smithy.linter.hints import (
    hint_check_spdx,
    hint_noarch_python_use_python_min,
    hint_os_version,
    hint_pip_no_build_backend,
    hint_pip_usage,
    hint_shellcheck_usage,
    hint_sources_should_not_mention_pypi_io_but_pypi_org,
    hint_space_separated_specs,
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
    lint_no_comment_selectors,
    lint_noarch,
    lint_noarch_and_runtime_dependencies,
    lint_non_noarch_builds,
    lint_package_version,
    lint_pin_subpackages,
    lint_recipe_have_tests,
    lint_recipe_is_abi3_bool,
    lint_recipe_is_parsable,
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
    flatten_v1_if_else,
    get_all_test_requirements,
    get_section,
    load_linter_toml_metdata,
)
from conda_smithy.utils import get_yaml, render_meta_yaml
from conda_smithy.validate_schema import validate_json_schema

NEEDED_FAMILIES = ["gpl", "bsd", "mit", "apache", "psf"]


def _get_forge_yaml(recipe_dir: Optional[str] = None) -> dict:
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
            with open(forge_yaml_filename[0], encoding="utf-8") as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        forge_yaml = {}

    return forge_yaml


def lintify_forge_yaml(recipe_dir: Optional[str] = None) -> (list, list):
    forge_yaml = _get_forge_yaml(recipe_dir)
    # This is where we validate against the jsonschema and execute our custom validators.
    return validate_json_schema(forge_yaml)


def lintify_meta_yaml(
    meta: Any,
    recipe_dir: Optional[str] = None,
    conda_forge: bool = False,
    recipe_version: int = 0,
) -> tuple[list[str], list[str]]:
    lints = []
    hints = []
    major_sections = list(meta.keys())
    lints_to_skip = (_get_forge_yaml(recipe_dir).get("linter") or {}).get("skip") or []

    # If the recipe_dir exists (no guarantee within this function) , we can
    # find the meta.yaml within it.
    recipe_name = "meta.yaml" if recipe_version == 0 else "recipe.yaml"
    recipe_fname = os.path.join(recipe_dir or "", recipe_name)

    if recipe_version == 1:
        schema_version = meta.get("schema_version", 1)
        if schema_version != 1:
            lints.append(f"Unsupported recipe.yaml schema version {schema_version}")
            return lints, hints

    sources_section = get_section(meta, "source", lints, recipe_version)
    build_section = get_section(meta, "build", lints, recipe_version)
    requirements_section = get_section(meta, "requirements", lints, recipe_version)
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

    # 6a: Comment-style selectors must not be used in v1 recipes.
    if recipe_version == 1:
        lint_no_comment_selectors(recipe_fname, lints, hints)

    # 7: The build section should have a build number.
    lint_build_section_should_have_a_number(build_section, lints)

    # 8: The build section should be before the run section in requirements.
    lint_build_section_should_be_before_run(requirements_section, lints)

    # 9: Files downloaded should have a hash.
    lint_sources_should_have_hash(sources_section, lints)

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
        recipe_name = conda_recipe_v1_linter.lint_recipe_name(meta, lints)
    else:
        recipe_name = lint_recipe_name(
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

        conda_build_config_filename = find_local_config_file(recipe_dir, cbc_file)

        if conda_build_config_filename:
            with open(conda_build_config_filename, encoding="utf-8") as fh:
                conda_build_config_keys = set(get_yaml().load(fh).keys())
        else:
            conda_build_config_keys = set()

        forge_yaml_filename = find_local_config_file(recipe_dir, "conda-forge.yml")

        if forge_yaml_filename:
            with open(forge_yaml_filename, encoding="utf-8") as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        conda_build_config_keys = set()
        forge_yaml = {}

    # 18: noarch doesn't work with selectors for runtime dependencies
    noarch_platforms = len(forge_yaml.get("noarch_platforms", [])) > 1
    if "lint_noarch_selectors" not in lints_to_skip:
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
    lint_single_space_in_pinned_requirements(
        requirements_section, lints, recipe_version
    )

    # 23: non noarch builds shouldn't use version constraints on python and r-base
    lint_non_noarch_builds(
        requirements_section,
        outputs_section,
        noarch_value,
        lints,
        recipe_version,
    )

    # 24: jinja2 variable references should be {{<one space>var<one space>}}
    lint_jinja_var_references(recipe_fname, hints, recipe_version=recipe_version)

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
        recipe_name, build_requirements, lints, recipe_version=recipe_version
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

    # 5: hint pypi.io -> pypi.org
    hint_sources_should_not_mention_pypi_io_but_pypi_org(sources_section, hints)

    # 6: stdlib-related lints
    if "lint_stdlib" not in lints_to_skip:
        lint_stdlib(
            meta,
            requirements_section,
            conda_build_config_filename,
            lints,
            hints,
            recipe_version=recipe_version,
        )

    # 7: warn of `name =version=build` specs, suggest `name version build`
    # see https://github.com/conda/conda-build/issues/5571#issuecomment-2604505922
    if recipe_version == 0:
        hint_space_separated_specs(
            requirements_section,
            test_section,
            outputs_section,
            hints,
        )

    # 8. check for obsolete os_version
    if "hint_os_version" not in lints_to_skip:
        hint_os_version(forge_yaml, hints)

    return lints, hints


# the two functions here allow the cache to refresh
# if some changes the value of os.environ["GH_TOKEN"]
# in the same Python process
@lru_cache(maxsize=1)
def _cached_gh_with_token(token: str) -> github.Github:
    return github.Github(auth=github.Auth.Token(token))


def _cached_gh() -> github.Github:
    return _cached_gh_with_token(os.environ["GH_TOKEN"])


def _maintainer_exists(maintainer: str) -> bool:
    """Check if a maintainer exists on GitHub."""
    if "GH_TOKEN" in os.environ:
        # use a token if we have one
        gh = _cached_gh()
        try:
            gh.get_user(maintainer)
            is_user = True
        except github.UnknownObjectException:
            is_user = False

        # for w/e reason, the user endpoint returns an entry for orgs
        # however the org endpoint does not return an entry for users
        # so we have to check both
        try:
            gh.get_organization(maintainer)
            is_org = True
        except github.UnknownObjectException:
            is_org = False
    else:
        # this API request has no token and so has a restrictive rate limit
        # return (
        #     requests.get(
        #         f"https://api.github.com/users/{maintainer}"
        #     ).status_code
        #     == 200
        # )
        # so we check two public URLs instead.
        # 1. github.com/<maintainer>?tab=repositories - this URL works for all users and all orgs
        # 2. https://github.com/orgs/<maintainer>/teams - this URL only works for
        #    orgs so we make sure it fails
        # we do not allow redirects to ensure we get the correct status code
        # for the specific URL we requested
        req_profile = requests.head(
            f"https://github.com/{maintainer}",
            allow_redirects=False,
        )
        is_user = req_profile.status_code == 200
        req_org = requests.head(
            f"https://github.com/orgs/{maintainer}/teams",
            allow_redirects=False,
        )
        is_org = req_org.status_code < 400

    return is_user and not is_org


@lru_cache(maxsize=1)
def _cached_gh_org(org: str) -> github.Organization.Organization:
    return _cached_gh().get_organization(org)


@lru_cache(maxsize=1)
def _cached_gh_team(org: str, team: str) -> github.Team.Team:
    return _cached_gh_org(org).get_team_by_slug(team)


def _team_exists(org_team: str) -> bool:
    """Check if a team exists on GitHub."""
    if "GH_TOKEN" in os.environ:
        _res = org_team.split("/", 1)
        if len(_res) != 2:
            return False
        org, team = _res
        try:
            _cached_gh_team(org, team)
        except github.UnknownObjectException:
            return False
        return True
    else:
        # we cannot check without a token
        return True


def run_conda_forge_specific(
    meta,
    recipe_dir,
    lints,
    hints,
    recipe_version: int = 0,
):
    lints_to_skip = (_get_forge_yaml(recipe_dir).get("linter") or {}).get("skip") or []

    # Retrieve sections from meta
    package_section = get_section(meta, "package", lints, recipe_version=recipe_version)
    extra_section = get_section(meta, "extra", lints, recipe_version=recipe_version)
    requirements_section = get_section(
        meta, "requirements", lints, recipe_version=recipe_version
    )
    outputs_section = get_section(meta, "outputs", lints, recipe_version=recipe_version)

    build_section = get_section(meta, "build", lints, recipe_version)
    noarch_value = build_section.get("noarch")
    test_reqs = get_all_test_requirements(meta, lints, recipe_version)

    # Fetch list of recipe maintainers
    maintainers = extra_section.get("recipe-maintainers", [])

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    if recipe_version == 1:
        recipe_name = conda_recipe_v1_linter.get_recipe_name(meta)
    else:
        recipe_name = package_section.get("name", "").strip()
    is_staged_recipes = recipe_dirname != "recipe"

    # 1: Check that the recipe does not exist in conda-forge or bioconda
    # moved to staged-recipes directly

    # 2: Check that the recipe maintainers exists:
    for maintainer in maintainers:
        if "/" in maintainer:
            if not _team_exists(maintainer):
                lints.append(f'Recipe maintainer team "{maintainer}" does not exist')
        else:
            if not _maintainer_exists(maintainer):
                lints.append(f'Recipe maintainer "{maintainer}" does not exist')

    # 3: if the recipe dir is inside the example dir
    # moved to staged-recipes directly

    # 4: Do not delete example recipe
    # removed in favor of direct check in staged-recipes CI

    # 5: Package-specific hints
    # (e.g. do not depend on matplotlib, only matplotlib-base)
    # we use a copy here since the += below mofiies the original list
    build_reqs = copy.deepcopy(requirements_section.get("build") or [])
    host_reqs = copy.deepcopy(requirements_section.get("host") or [])
    run_reqs = copy.deepcopy(requirements_section.get("run") or [])
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

    specific_hints = (load_linter_toml_metdata() or {}).get("hints", [])
    all_reqs = build_reqs + host_reqs + run_reqs
    if recipe_version == 1:
        all_reqs = flatten_v1_if_else(all_reqs)

    for rq in all_reqs:
        dep = rq.split(" ")[0].strip()
        if dep in specific_hints and specific_hints[dep] not in hints:
            hints.append(specific_hints[dep])

    # 6: Check if all listed maintainers have commented:
    # moved to staged recipes directly

    # 7: Ensure that the recipe has some .ci_support files
    if not is_staged_recipes and recipe_dir is not None:
        ci_support_files = glob(os.path.join(recipe_dir, "..", ".ci_support", "*.yaml"))
        if not ci_support_files:
            lints.append(
                "The feedstock has no `.ci_support` files and thus will not build any packages."
            )

    # 8: Ensure the recipe specifies a Python build backend if needed
    if "hint_pip_no_build_backend" not in lints_to_skip:
        host_or_build_reqs = (requirements_section.get("host") or []) or (
            requirements_section.get("build") or []
        )
        if recipe_version == 1:
            host_or_build_reqs = flatten_v1_if_else(host_or_build_reqs)
        hint_pip_no_build_backend(host_or_build_reqs, recipe_name, hints)
        for out in outputs_section:
            if recipe_version == 1:
                output_requirements = rattler_loader.load_all_requirements(out)
                build_reqs = output_requirements.get("build") or []
                host_reqs = output_requirements.get("host") or []
            else:
                _req = out.get("requirements") or {}
                if isinstance(_req, Mapping):
                    build_reqs = _req.get("build") or []
                    host_reqs = _req.get("host") or []
                else:
                    build_reqs = []
                    host_reqs = []

            name = out.get("name", "").strip()
            hint_pip_no_build_backend(host_reqs or build_reqs, name, hints)

    # 9: No duplicates in conda-forge.yml
    if (
        not is_staged_recipes
        and recipe_dir is not None
        and os.path.exists(
            cfyml_pth := os.path.join(recipe_dir, "..", "conda-forge.yml")
        )
    ):
        try:
            with open(cfyml_pth, encoding="utf-8") as fh:
                get_yaml(allow_duplicate_keys=False).load(fh)
        except DuplicateKeyError:
            lints.append(
                "The ``conda-forge.yml`` file is not allowed to have duplicate keys."
            )

    # 10: check for proper noarch python syntax
    if "hint_python_min" not in lints_to_skip:
        hint_noarch_python_use_python_min(
            requirements_section.get("host") or [],
            requirements_section.get("run") or [],
            test_reqs,
            outputs_section,
            noarch_value,
            recipe_version,
            hints,
        )

    if recipe_version == 1:
        recipe_fname = os.path.join(recipe_dir or "", "recipe.yaml")
    else:
        recipe_fname = os.path.join(recipe_dir or "", "meta.yaml")

    if os.path.exists(recipe_fname):
        with open(recipe_fname, encoding="utf-8") as fh:
            recipe_text = fh.read()

        # 11: ensure we can parse the recipe
        lint_recipe_is_parsable(
            recipe_text,
            lints,
            hints,
            recipe_version=recipe_version,
        )

        # 12: ensure is_abi3 is boolean
        lint_recipe_is_abi3_bool(
            recipe_text,
            lints,
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


def find_recipe_directory(
    recipe_dir: str,
    feedstock_dir: Optional[str],
) -> tuple[str, str]:
    """Find recipe directory and build tool"""

    recipe_dir = os.path.abspath(recipe_dir)
    build_tool = CONDA_BUILD_TOOL

    # The logic below:
    # 1. If `--feedstock-dir` is not specified, try looking for `recipe.yaml`
    #    or `meta.yaml` in the specified recipe directory.
    # 2. If there is none, look for `conda-forge.yml` -- perhaps the user
    #    passed feedstock directory instead.  In that case, obtain
    #    the recipe directory from `conda-forge.yml`.

    if feedstock_dir is None:
        if os.path.exists(os.path.join(recipe_dir, "recipe.yaml")):
            return (recipe_dir, RATTLER_BUILD_TOOL)
        elif os.path.exists(os.path.join(recipe_dir, "meta.yaml")):
            return (recipe_dir, CONDA_BUILD_TOOL)
        elif os.path.exists(os.path.join(recipe_dir, "conda-forge.yml")):
            # passthrough to the feedstock_dir logic below
            feedstock_dir = recipe_dir
            recipe_dir = None

    if feedstock_dir is not None:
        feedstock_dir = os.path.abspath(feedstock_dir)
        forge_config = _read_forge_config(feedstock_dir)
        if forge_config.get("conda_build_tool", "") == RATTLER_BUILD_TOOL:
            build_tool = RATTLER_BUILD_TOOL
        if recipe_dir is None:
            recipe_dir = os.path.join(
                feedstock_dir, forge_config.get("recipe_dir", "recipe")
            )

    return (recipe_dir, build_tool)


def main(recipe_dir, conda_forge=False, return_hints=False, feedstock_dir=None):
    recipe_dir, build_tool = find_recipe_directory(recipe_dir, feedstock_dir)

    if build_tool == RATTLER_BUILD_TOOL:
        recipe_file = os.path.join(recipe_dir, "recipe.yaml")
    else:
        recipe_file = os.path.join(recipe_dir, "meta.yaml")

    if not os.path.exists(recipe_file):
        raise OSError(f"No recipe file found in {recipe_dir}")

    if build_tool == CONDA_BUILD_TOOL:
        with open(recipe_file, encoding="utf-8") as fh:
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
    validation_errors, validation_hints = lintify_forge_yaml(recipe_dir=recipe_dir)

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
                rel_path, "\n".join(f"* ❌ {lint}" for lint in lints)
            )
        )
    if hints:
        messages.append(
            "\nFor **{}**:\n\n{}".format(
                rel_path, "\n".join(f"* ℹ️ {hint}" for hint in hints)
            )
        )

    print(*messages, sep="\n")
