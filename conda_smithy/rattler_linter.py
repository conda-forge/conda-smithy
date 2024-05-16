import os
import re


import sys
from typing import Dict, List, Mapping

import github
import requests

from rattler_build_conda_compat.loader import load_yaml
from conda.models.version import VersionOrder

if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib

REQUIREMENTS_ORDER = ["build", "host", "run"]
EXPECTED_SINGLE_OUTPUT_SECTION_ORDER = [
    "context",
    "package",
    "source",
    "build",
    "requirements",
    "tests",
    "about",
    "extra",
]

EXPECTED_MUTIPLE_OUTPUT_SECTION_ORDER = [
    "context",
    "recipe",
    "source",
    "build",
    "outputs",
    "about",
    "extra",
]


JINJA_VAR_PAT = re.compile(r"\${{(.*?)}}")


def _is_keys_in_order(input_dict, expected_order):
    # Filter the keys of the input dictionary based on the expected order
    filtered_keys = [key for key in expected_order if key in input_dict]

    # Create a list of the keys in the input dictionary in their actual order
    actual_keys = list(input_dict.keys())

    # Check if the filtered keys are in the same order as they appear in the actual keys
    index = 0
    for key in filtered_keys:
        try:
            index = actual_keys.index(key, index)
        except ValueError:
            return False
        index += 1

    return True


def lint_section_order(major_sections, lints):
    expected_section = (
        EXPECTED_MUTIPLE_OUTPUT_SECTION_ORDER
        if "outputs" in major_sections
        else EXPECTED_SINGLE_OUTPUT_SECTION_ORDER
    )

    in_order = _is_keys_in_order(major_sections, expected_section)

    if not in_order:
        section_order_sorted_str = map(lambda s: "'%s'" % s, expected_section)
        section_order_sorted_str = ", ".join(section_order_sorted_str)
        section_order_sorted_str = "[" + section_order_sorted_str + "]"
        lints.append(
            "The top level meta keys are in an unexpected order. "
            "Expecting {}.".format(section_order_sorted_str)
        )


def lint_about_contents(about_section, lints):
    for about_item in ["homepage", "license", "summary"]:
        # if the section doesn't exist, or is just empty, lint it.
        if not about_section.get(about_item, ""):
            lints.append(
                "The {} item is expected in the about section."
                "".format(about_item)
            )


def lint_recipe_tests(test_section=dict(), outputs_section=list()):
    TEST_KEYS = {"script", "python"}
    lints = []
    hints = []

    if not any(key in TEST_KEYS for key in test_section):
        if not outputs_section:
            lints.append("The recipe must have some tests.")
        else:
            has_outputs_test = False
            no_test_hints = []
            for section in outputs_section:
                test_section = section.get("tests", {})
                if any(key in TEST_KEYS for key in test_section):
                    has_outputs_test = True
                else:
                    no_test_hints.append(
                        "It looks like the '{}' output doesn't "
                        "have any tests.".format(section.get("name", "???"))
                    )
            if has_outputs_test:
                hints.extend(no_test_hints)
            else:
                lints.append("The recipe must have some tests.")

    return lints, hints


def lint_requirements_order(requirements_section: Dict, lints: List):
    seen_requirements = [
        k for k in requirements_section if k in REQUIREMENTS_ORDER
    ]
    requirements_order_sorted = sorted(
        seen_requirements, key=REQUIREMENTS_ORDER.index
    )
    if seen_requirements != requirements_order_sorted:
        lints.append(
            "The `requirements/` sections should be defined "
            "in the following order: "
            + ", ".join(REQUIREMENTS_ORDER)
            + "; instead saw: "
            + ", ".join(seen_requirements)
            + "."
        )


def lint_has_recipe_file(about_section, lints):
    license_file = about_section.get("license_file", None)
    if not license_file:
        lints.append("license_file entry is missing, but is required.")


def lint_package_name(package_section: Dict, context_section: Dict):
    package_name = str(package_section.get("name"))
    context_name = str(context_section.get("name"))
    actual_name = (
        package_name
        if package_name is not None and not package_name.startswith("$")
        else context_name
    )

    actual_name = actual_name.strip()
    if re.match(r"^[a-z0-9_\-.]+$", actual_name) is None:
        return """Recipe name has invalid characters. only lowercase alpha, numeric, underscores, hyphens and dots allowed"""


def run_conda_forge_specific(
    recipe_dir,
    package_section,
    extra_section,
    sources_section,
    requirements_section,
    outputs_section,
):
    lints = []
    hints = []

    gh = github.Github(os.environ["GH_TOKEN"])

    # Fetch list of recipe maintainers
    maintainers = extra_section.get("recipe-maintainers", [])

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
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
                if cf.get_repo("{}-feedstock".format(name)):
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
                "Feedstock with the name {} exists in conda-forge. Is it the same as this package ({})?".format(
                    existing_recipe_name,
                    recipe_name,
                )
            )

        bio = gh.get_user("bioconda").get_repo("bioconda-recipes")
        try:
            bio.get_dir_contents("recipes/{}".format(recipe_name))
        except github.UnknownObjectException:
            pass
        else:
            hints.append(
                "Recipe with the same name exists in bioconda: "
                "please discuss with @conda-forge/bioconda-recipes."
            )

        url = None
        if isinstance(sources_section, dict):
            if str(sources_section.get("url")).startswith(
                "https://pypi.io/packages/source/"
            ):
                url = sources_section["url"]
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
                mapping = load_yaml(mapping_raw_yaml)
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
            lints.append(
                'Recipe maintainer "{}" does not exist'.format(maintainer)
            )

    # 3: if the recipe dir is inside the example dir
    if recipe_dir is not None and "recipes/example/" in recipe_dir:
        lints.append(
            "Please move the recipe out of the example dir and "
            "into its own dir."
        )

    # 4: Do not delete example recipe
    if is_staged_recipes and recipe_dir is not None:
        example_meta_fname = os.path.abspath(
            os.path.join(recipe_dir, "..", "example", "meta.yaml")
        )

        if not os.path.exists(example_meta_fname):
            msg = (
                "Please do not delete the example recipe found in "
                "`recipes/example/meta.yaml`."
            )

            if msg not in lints:
                lints.append(msg)

    # 5: Package-specific hints
    # (e.g. do not depend on matplotlib, only matplotlib-base)
    # TODO: do the same for if selectors
    build_reqs = requirements_section.get("build") or []
    host_reqs = requirements_section.get("host") or []
    run_reqs = requirements_section.get("run") or []
    for out in outputs_section:
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

    return lints, hints


def lint_legacy_patterns(requirements_section):
    lints = []
    build_reqs = requirements_section.get("build", None)
    if build_reqs and ("numpy x.x" in build_reqs):
        lints.append(
            "Using pinned numpy packages is a deprecated pattern.  Consider "
            "using the method outlined "
            "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy)."
        )
    return lints


def lint_usage_of_selectors_for_noarch(
    noarch_value, build_section, requirements_section
):
    lints = []
    for section in requirements_section:
        section_requirements = requirements_section[section]

        if not section_requirements:
            continue

        if any(isinstance(req, dict) for req in section_requirements):
            lints.append(
                "`noarch` packages can't have skips with selectors. If "
                "the selectors are necessary, please remove "
                "`noarch: {}`.".format(noarch_value)
            )
            break

    if "skip" in build_section:
        lints.append(
            "`noarch` packages can't have skips with selectors. If "
            "the selectors are necessary, please remove "
            "`noarch: {}`.".format(noarch_value)
        )

    return lints


def lint_package_version(package_section: dict, context_section: dict):
    package_ver = str(package_section.get("version"))
    context_ver = str(context_section.get("version"))
    ver = (
        package_ver
        if package_ver is not None and not package_ver.startswith("$")
        else context_ver
    )

    try:
        VersionOrder(ver)

    except Exception:
        return "Package version {} doesn't match conda spec".format(ver)


def lint_legacy_compilers(build_reqs):
    if build_reqs and ("toolchain" in build_reqs):
        return """Using toolchain directly in this manner is deprecated. Consider
            using the compilers outlined
            [here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers)."""


def lint_usage_of_single_space_in_pinned_requirements(
    requirements_section: dict,
):
    def verify_requirement(requirement, section):
        lints = []
        if "${{" in requirement:
            return lints
        parts = requirement.split()
        if len(parts) > 2 and parts[1] in [
            "!=",
            "=",
            "==",
            ">",
            "<",
            "<=",
            ">=",
        ]:
            # check for too many spaces
            lints.append(
                (
                    "``requirements: {section}: {requirement}`` should not "
                    "contain a space between relational operator and the version, i.e. "
                    "``{name} {pin}``"
                ).format(
                    section=section,
                    requirement=requirement,
                    name=parts[0],
                    pin="".join(parts[1:]),
                )
            )
            return lints
        # check that there is a space if there is a pin
        bad_char_idx = [(parts[0].find(c), c) for c in "><="]
        bad_char_idx = [bci for bci in bad_char_idx if bci[0] >= 0]
        if bad_char_idx:
            bad_char_idx.sort()
            i = bad_char_idx[0][0]
            lints.append(
                (
                    "``requirements: {section}: {requirement}`` must "
                    "contain a space between the name and the pin, i.e. "
                    "``{name} {pin}``"
                ).format(
                    section=section,
                    requirement=requirement,
                    name=parts[0][:i],
                    pin=parts[0][i:] + "".join(parts[1:]),
                )
            )

        return lints

    lints = []
    for section, requirements in requirements_section.items():
        if not requirements:
            continue
        for req in requirements:
            lints.extend(verify_requirement(req, section))
    return lints


def lint_non_noarch_dont_constrain_python_and_rbase(requirements_section):
    check_languages = ["python", "r-base"]
    host_reqs = requirements_section.get("host") or []
    run_reqs = requirements_section.get("run") or []

    lints = []

    for language in check_languages:
        filtered_host_reqs = [
            req for req in host_reqs if req.startswith(f"{language}")
        ]
        filtered_run_reqs = [
            req for req in run_reqs if req.startswith(f"{language}")
        ]

        if filtered_host_reqs and not filtered_run_reqs:
            lints.append(
                f"If {language} is a host requirement, it should be a run requirement."
            )

        for reqs in [filtered_host_reqs, filtered_run_reqs]:
            if language not in reqs:
                for req in reqs:
                    splitted = req.split(" ", 1)
                    if len(splitted) > 1:
                        constraint = req.split(" ", 1)[1]
                        if constraint.startswith(">") or constraint.startswith(
                            "<"
                        ):
                            lints.append(
                                f"Non noarch packages should have {language} requirement without any version constraints."
                            )

    return lints


def lint_variable_reference_should_have_space(recipe_dir, recipe_file):
    hints = []
    if recipe_dir is not None and os.path.exists(recipe_file):
        bad_vars = []
        bad_lines = []
        with open(recipe_file, "r") as fh:
            for i, line in enumerate(fh.readlines()):
                for m in JINJA_VAR_PAT.finditer(line):
                    if m.group(1) is not None:
                        var = m.group(1)
                        if var != " %s " % var.strip():
                            bad_vars.append(m.group(1).strip())
                            bad_lines.append(i + 1)
        if bad_vars:
            hints.append(
                "Jinja2 variable references are suggested to "
                "take a ``${{<one space><variable name><one space>}}``"
                " form. See lines %s." % (bad_lines,)
            )

    return hints


def lint_lower_bound_on_python(run_requirements, outputs_section):
    lints = []
    # if noarch_value == "python" and not outputs_section:
    for req in run_requirements:
        if (req.strip().split()[0] == "python") and (req != "python"):
            break
    else:
        lints.append(
            "noarch: python recipes are required to have a lower bound "
            "on the python version. Typically this means putting "
            "`python >=3.6` in **both** `host` and `run` but you should check "
            "upstream for the package's Python compatibility."
        )


def hint_pip_usage(build_section):
    hints = []

    if "script" in build_section:
        scripts = build_section["script"]
        if isinstance(scripts, str):
            scripts = [scripts]
        for script in scripts:
            if "python setup.py install" in script:
                hints.append(
                    "Whenever possible python packages should use pip. "
                    "See https://conda-forge.org/docs/maintainer/adding_pkgs.html#use-pip"
                )
    return hints


def hint_noarch_usage(build_section, requirement_section: dict):
    build_reqs = requirement_section.get("build", None)
    hints = []
    if (
        # move outside the call
        # noarch_value is None
        build_reqs
        and not any(
            [
                b.startswith("${{")
                and ("compiler('c')" in b or 'compiler("c")' in b)
                for b in build_reqs
            ]
        )
        and ("pip" in build_reqs)
        # move outside the call
        # and (is_staged_recipes or not conda_forge)
    ):
        no_arch_possible = True
        if "skip" in build_section:
            no_arch_possible = False

        for _, section_requirements in requirement_section.items():
            if any(
                isinstance(requirement, dict)
                for requirement in section_requirements
            ):
                no_arch_possible = False
                break

        if no_arch_possible:
            hints.append(
                "Whenever possible python packages should use noarch. "
                "See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds"
            )

    return hints
