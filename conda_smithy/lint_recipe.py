# -*- coding: utf-8 -*-

from collections.abc import Sequence, Mapping

str_type = str

import copy
from glob import glob
import io
import itertools
import os
import re
import shutil
import subprocess
import sys

import github

from conda_build.metadata import (
    ensure_valid_license_family,
    FIELDS as cbfields,
)
import conda_build.conda_interface

from .utils import render_meta_yaml, get_yaml


FIELDS = copy.deepcopy(cbfields)

# Just in case 'extra' moves into conda_build
if "extra" not in FIELDS.keys():
    FIELDS["extra"] = set()

FIELDS["extra"].add("recipe-maintainers")

EXPECTED_SECTION_ORDER = [
    "package",
    "source",
    "build",
    "requirements",
    "test",
    "app",
    "outputs",
    "about",
    "extra",
]

REQUIREMENTS_ORDER = ["build", "host", "run"]

TEST_KEYS = {"imports", "commands"}
TEST_FILES = ["run_test.py", "run_test.sh", "run_test.bat", "run_test.pl"]


NEEDED_FAMILIES = ["gpl", "bsd", "mit", "apache", "psf"]

sel_pat = re.compile(r"(.+?)\s*(#.*)?\[([^\[\]]+)\](?(2).*)$")
jinja_pat = re.compile(r"\s*\{%\s*(set)\s+[^\s]+\s*=\s*[^\s]+\s*%\}")
JINJA_VAR_PAT = re.compile(r"{{(.*?)}}")


def get_section(parent, name, lints):
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


def get_list_section(parent, name, lints, allow_single=False):
    section = parent.get(name, [])
    if allow_single and isinstance(section, Mapping):
        return [section]
    elif isinstance(section, Sequence) and not isinstance(section, str_type):
        return section
    else:
        msg = 'The "{}" section was expected to be a {}list, but got a {}.{}.'.format(
            name,
            "dictionary or a " if allow_single else "",
            type(section).__module__,
            type(section).__name__,
        )
        lints.append(msg)
        return [{}]


def lint_section_order(major_sections, lints):
    section_order_sorted = sorted(
        major_sections, key=EXPECTED_SECTION_ORDER.index
    )
    if major_sections != section_order_sorted:
        section_order_sorted_str = map(
            lambda s: "'%s'" % s, section_order_sorted
        )
        section_order_sorted_str = ", ".join(section_order_sorted_str)
        section_order_sorted_str = "[" + section_order_sorted_str + "]"
        lints.append(
            "The top level meta keys are in an unexpected order. "
            "Expecting {}.".format(section_order_sorted_str)
        )


def lint_about_contents(about_section, lints):
    for about_item in ["home", "license", "summary"]:
        # if the section doesn't exist, or is just empty, lint it.
        if not about_section.get(about_item, ""):
            lints.append(
                "The {} item is expected in the about section."
                "".format(about_item)
            )


def lintify(meta, recipe_dir=None, conda_forge=False):
    lints = []
    hints = []
    major_sections = list(meta.keys())

    # If the recipe_dir exists (no guarantee within this function) , we can
    # find the meta.yaml within it.
    meta_fname = os.path.join(recipe_dir or "", "meta.yaml")

    sources_section = get_section(meta, "source", lints)
    build_section = get_section(meta, "build", lints)
    requirements_section = get_section(meta, "requirements", lints)
    test_section = get_section(meta, "test", lints)
    about_section = get_section(meta, "about", lints)
    extra_section = get_section(meta, "extra", lints)
    package_section = get_section(meta, "package", lints)
    outputs_section = get_section(meta, "outputs", lints)

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    is_staged_recipes = recipe_dirname != "recipe"

    # 0: Top level keys should be expected
    unexpected_sections = []
    for section in major_sections:
        if section not in EXPECTED_SECTION_ORDER:
            lints.append(
                "The top level meta key {} is unexpected".format(section)
            )
            unexpected_sections.append(section)

    for section in unexpected_sections:
        major_sections.remove(section)

    # 1: Top level meta.yaml keys should have a specific order.
    lint_section_order(major_sections, lints)

    # 2: The about section should have a home, license and summary.
    lint_about_contents(about_section, lints)

    # 3a: The recipe should have some maintainers.
    if not extra_section.get("recipe-maintainers", []):
        lints.append(
            "The recipe could do with some maintainers listed in "
            "the `extra/recipe-maintainers` section."
        )

    # 3b: Maintainers should be a list
    if not (
        isinstance(extra_section.get("recipe-maintainers", []), Sequence)
        and not isinstance(
            extra_section.get("recipe-maintainers", []), str_type
        )
    ):
        lints.append("Recipe maintainers should be a json list.")

    # 4: The recipe should have some tests.
    if not any(key in TEST_KEYS for key in test_section):
        a_test_file_exists = recipe_dir is not None and any(
            os.path.exists(os.path.join(recipe_dir, test_file))
            for test_file in TEST_FILES
        )
        if not a_test_file_exists:
            has_outputs_test = False
            no_test_hints = []
            if outputs_section:
                for out in outputs_section:
                    test_out = get_section(out, "test", lints)
                    if any(key in TEST_KEYS for key in test_out):
                        has_outputs_test = True
                    else:
                        no_test_hints.append(
                            "It looks like the '{}' output doesn't "
                            "have any tests.".format(out.get("name", "???"))
                        )

            if has_outputs_test:
                hints.extend(no_test_hints)
            else:
                lints.append("The recipe must have some tests.")

    # 5: License cannot be 'unknown.'
    license = about_section.get("license", "").lower()
    if "unknown" == license.strip():
        lints.append("The recipe license cannot be unknown.")

    # 6: Selectors should be in a tidy form.
    if recipe_dir is not None and os.path.exists(meta_fname):
        bad_selectors = []
        bad_lines = []
        # Good selectors look like ".*\s\s#\s[...]"
        good_selectors_pat = re.compile(r"(.+?)\s{2,}#\s\[(.+)\](?(2).*)$")
        with io.open(meta_fname, "rt") as fh:
            for selector_line, line_number in selector_lines(fh):
                if not good_selectors_pat.match(selector_line):
                    bad_selectors.append(selector_line)
                    bad_lines.append(line_number)
        if bad_selectors:
            lints.append(
                "Selectors are suggested to take a "
                "``<two spaces>#<one space>[<expression>]`` form."
                " See lines {}".format(bad_lines)
            )

    # 7: The build section should have a build number.
    if build_section.get("number", None) is None:
        lints.append("The recipe must have a `build/number` section.")

    # 8: The build section should be before the run section in requirements.
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

    # 9: Files downloaded should have a hash.
    for source_section in sources_section:
        if "url" in source_section and not (
            {"sha1", "sha256", "md5"} & set(source_section.keys())
        ):
            lints.append(
                "When defining a source/url please add a sha256, sha1 "
                "or md5 checksum (sha256 preferably)."
            )

    # 10: License should not include the word 'license'.
    license = about_section.get("license", "").lower()
    if (
        "license" in license.lower()
        and "unlicense" not in license.lower()
        and "licenseref" not in license.lower()
        and "-license" not in license.lower()
    ):
        lints.append(
            "The recipe `license` should not include the word " '"License".'
        )

    # 11: There should be one empty line at the end of the file.
    if recipe_dir is not None and os.path.exists(meta_fname):
        with io.open(meta_fname, "r") as f:
            lines = f.read().split("\n")
        # Count the number of empty lines from the end of the file
        empty_lines = itertools.takewhile(lambda x: x == "", reversed(lines))
        end_empty_lines_count = len(list(empty_lines))
        if end_empty_lines_count > 1:
            lints.append(
                "There are {} too many lines.  "
                "There should be one empty line at the end of the "
                "file.".format(end_empty_lines_count - 1)
            )
        elif end_empty_lines_count < 1:
            lints.append(
                "There are too few lines.  There should be one empty "
                "line at the end of the file."
            )

    # 12: License family must be valid (conda-build checks for that)
    try:
        ensure_valid_license_family(meta)
    except RuntimeError as e:
        lints.append(str(e))

    # 12a: License family must be valid (conda-build checks for that)
    license_family = about_section.get("license_family", license).lower()
    license_file = about_section.get("license_file", None)
    if not license_file:
        lints.append("license_file entry is missing, but is required.")

    # 13: Check that the recipe name is valid
    recipe_name = package_section.get("name", "").strip()
    if re.match("^[a-z0-9_\-.]+$", recipe_name) is None:
        lints.append(
            "Recipe name has invalid characters. only lowercase alpha, numeric, "
            "underscores, hyphens and dots allowed"
        )

    # 14: Run conda-forge specific lints
    if conda_forge:
        run_conda_forge_specific(meta, recipe_dir, lints, hints)

    # 15: Check if we are using legacy patterns
    build_reqs = requirements_section.get("build", None)
    if build_reqs and ("numpy x.x" in build_reqs):
        lints.append(
            "Using pinned numpy packages is a deprecated pattern.  Consider "
            "using the method outlined "
            "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy)."
        )

    # 16: Subheaders should be in the allowed subheadings
    for section in major_sections:
        expected_subsections = FIELDS.get(section, [])
        if not expected_subsections:
            continue
        for subsection in get_section(meta, section, lints):
            if (
                section != "source"
                and section != "outputs"
                and subsection not in expected_subsections
            ):
                lints.append(
                    "The {} section contained an unexpected "
                    "subsection name. {} is not a valid subsection"
                    " name.".format(section, subsection)
                )
            elif section == "source" or section == "outputs":
                for source_subsection in subsection:
                    if source_subsection not in expected_subsections:
                        lints.append(
                            "The {} section contained an unexpected "
                            "subsection name. {} is not a valid subsection"
                            " name.".format(section, source_subsection)
                        )

    # 17: noarch doesn't work with selectors for runtime dependencies
    if build_section.get("noarch") is not None and os.path.exists(meta_fname):
        with io.open(meta_fname, "rt") as fh:
            in_runreqs = False
            for line in fh:
                line_s = line.strip()
                if line_s == "host:" or line_s == "run:":
                    in_runreqs = True
                    runreqs_spacing = line[: -len(line.lstrip())]
                    continue
                if line_s.startswith("skip:") and is_selector_line(line):
                    lints.append(
                        "`noarch` packages can't have selectors. If "
                        "the selectors are necessary, please remove "
                        "`noarch: {}`.".format(build_section["noarch"])
                    )
                    break
                if in_runreqs:
                    if runreqs_spacing == line[: -len(line.lstrip())]:
                        in_runreqs = False
                        continue
                    if is_selector_line(line):
                        lints.append(
                            "`noarch` packages can't have selectors. If "
                            "the selectors are necessary, please remove "
                            "`noarch: {}`.".format(build_section["noarch"])
                        )
                        break

    # 19: check version
    if package_section.get("version") is not None:
        ver = str(package_section.get("version"))
        try:
            conda_build.conda_interface.VersionOrder(ver)
        except:
            lints.append(
                "Package version {} doesn't match conda spec".format(ver)
            )

    # 20: Jinja2 variable definitions should be nice.
    if recipe_dir is not None and os.path.exists(meta_fname):
        bad_jinja = []
        bad_lines = []
        # Good Jinja2 variable definitions look like "{% set .+ = .+ %}"
        good_jinja_pat = re.compile(r"\s*\{%\s(set)\s[^\s]+\s=\s[^\s]+\s%\}")
        with io.open(meta_fname, "rt") as fh:
            for jinja_line, line_number in jinja_lines(fh):
                if not good_jinja_pat.match(jinja_line):
                    bad_jinja.append(jinja_line)
                    bad_lines.append(line_number)
        if bad_jinja:
            lints.append(
                "Jinja2 variable definitions are suggested to "
                "take a ``{{%<one space>set<one space>"
                "<variable name><one space>=<one space>"
                "<expression><one space>%}}`` form. See lines "
                "{}".format(bad_lines)
            )

    # 21: Legacy usage of compilers
    if build_reqs and ("toolchain" in build_reqs):
        lints.append(
            "Using toolchain directly in this manner is deprecated.  Consider "
            "using the compilers outlined "
            "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers)."
        )

    # 22: Single space in pinned requirements
    for section, requirements in requirements_section.items():
        for requirement in requirements or []:
            req, _, _ = requirement.partition("#")
            if "{{" in req:
                continue
            parts = req.split()
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
                continue
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
                continue

    # 23: non noarch builds shouldn't use version constraints on python and r-base
    check_languages = ["python", "r-base"]
    host_reqs = requirements_section.get("host") or []
    run_reqs = requirements_section.get("run") or []
    for language in check_languages:
        if build_section.get("noarch") is None and not outputs_section:
            filtered_host_reqs = [
                req
                for req in host_reqs
                if req.partition(" ")[0] == str(language)
            ]
            filtered_run_reqs = [
                req
                for req in run_reqs
                if req.partition(" ")[0] == str(language)
            ]
            if filtered_host_reqs and not filtered_run_reqs:
                lints.append(
                    "If {0} is a host requirement, it should be a run requirement.".format(
                        str(language)
                    )
                )
            for reqs in [filtered_host_reqs, filtered_run_reqs]:
                if str(language) in reqs:
                    continue
                for req in reqs:
                    constraint = req.split(" ", 1)[1]
                    if constraint.startswith(">") or constraint.startswith(
                        "<"
                    ):
                        lints.append(
                            "Non noarch packages should have {0} requirement without any version constraints.".format(
                                str(language)
                            )
                        )

    # 24: jinja2 variable references should be {{<one space>var<one space>}}
    if recipe_dir is not None and os.path.exists(meta_fname):
        bad_vars = []
        bad_lines = []
        with io.open(meta_fname, "rt") as fh:
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
                "take a ``{{<one space><variable name><one space>}}``"
                " form. See lines %s." % (bad_lines,)
            )

    # hints
    # 1: suggest pip
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

    # 2: suggest python noarch (skip on feedstocks)
    if (
        build_section.get("noarch") is None
        and build_reqs
        and not any(["_compiler_stub" in b for b in build_reqs])
        and ("pip" in build_reqs)
        and (is_staged_recipes or not conda_forge)
    ):
        with io.open(meta_fname, "rt") as fh:
            in_runreqs = False
            no_arch_possible = True
            for line in fh:
                line_s = line.strip()
                if line_s == "host:" or line_s == "run:":
                    in_runreqs = True
                    runreqs_spacing = line[: -len(line.lstrip())]
                    continue
                if line_s.startswith("skip:") and is_selector_line(line):
                    no_arch_possible = False
                    break
                if in_runreqs:
                    if runreqs_spacing == line[: -len(line.lstrip())]:
                        in_runreqs = False
                        continue
                    if is_selector_line(line):
                        no_arch_possible = False
                        break
            if no_arch_possible:
                hints.append(
                    "Whenever possible python packages should use noarch. "
                    "See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-builds"
                )

    # 3: suggest fixing all recipe/*.sh shellcheck findings
    shellcheck_enabled = False
    shell_scripts = []
    if recipe_dir:
        shell_scripts = glob(os.path.join(recipe_dir, "*.sh"))
        # support feedstocks and staged-recipes
        forge_yaml = glob(
            os.path.join(recipe_dir, "..", "conda-forge.yml")
        ) or glob(os.path.join(recipe_dir, "..", "..", "conda-forge.yml"),)
        if shell_scripts and forge_yaml:
            with open(forge_yaml[0], "r") as fh:
                code = get_yaml().load(fh)
                shellcheck_enabled = code.get("shellcheck", {}).get(
                    "enabled", shellcheck_enabled
                )

    if shellcheck_enabled and shutil.which("shellcheck") and shell_scripts:
        MAX_SHELLCHECK_LINES = 50
        cmd = [
            "shellcheck",
            "--enable=all",
            "--shell=bash",
            # SC2154: var is referenced but not assigned,
            #         see https://github.com/koalaman/shellcheck/wiki/SC2154
            "--exclude=SC2154",
        ]

        p = subprocess.Popen(
            cmd + shell_scripts,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={
                "PATH": os.getenv("PATH")
            },  # exclude other env variables to protect against token leakage
        )
        sc_stdout, _ = p.communicate()

        if p.returncode == 1:
            # All files successfully scanned with some issues.
            findings = (
                sc_stdout.decode(sys.stdout.encoding)
                .replace("\r\n", "\n")
                .splitlines()
            )
            hints.append(
                "Whenever possible fix all shellcheck findings ('"
                + " ".join(cmd)
                + " recipe/*.sh -f diff | git apply' helps)"
            )
            hints.extend(findings[:50])
            if len(findings) > MAX_SHELLCHECK_LINES:
                hints.append(
                    "Output restricted, there are '%s' more lines."
                    % (len(findings) - MAX_SHELLCHECK_LINES)
                )
        elif p.returncode != 0:
            # Something went wrong.
            hints.append(
                "There have been errors while scanning with shellcheck."
            )

    # 4: Check for SPDX
    import license_expression

    license = about_section.get("license", "")
    licensing = license_expression.Licensing()
    parsed_exceptions = []
    try:
        parsed_licenses = []
        parsed_licenses_with_exception = licensing.license_symbols(
            license.strip(), decompose=False
        )
        for l in parsed_licenses_with_exception:
            if isinstance(l, license_expression.LicenseWithExceptionSymbol):
                parsed_licenses.append(l.license_symbol.key)
                parsed_exceptions.append(l.exception_symbol.key)
            else:
                parsed_licenses.append(l.key)
    except license_expression.ExpressionError:
        parsed_licenses = [license]

    licenseref_regex = re.compile("^LicenseRef[a-zA-Z0-9\-.]*$")
    filtered_licenses = []
    for license in parsed_licenses:
        if not licenseref_regex.match(license):
            filtered_licenses.append(license)

    with open(
        os.path.join(os.path.dirname(__file__), "licenses.txt"), "r"
    ) as f:
        expected_licenses = f.readlines()
        expected_licenses = set([l.strip() for l in expected_licenses])
    with open(
        os.path.join(os.path.dirname(__file__), "license_exceptions.txt"), "r"
    ) as f:
        expected_exceptions = f.readlines()
        expected_exceptions = set([l.strip() for l in expected_exceptions])
    if set(filtered_licenses) - expected_licenses:
        hints.append(
            "License is not an SPDX identifier (or a custom LicenseRef) nor an SPDX license expression."
        )
    if set(parsed_exceptions) - expected_exceptions:
        hints.append("License exception is not an SPDX exception.")

    return lints, hints


def run_conda_forge_specific(meta, recipe_dir, lints, hints):
    gh = github.Github(os.environ["GH_TOKEN"])
    package_section = get_section(meta, "package", lints)
    extra_section = get_section(meta, "extra", lints)
    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    recipe_name = package_section.get("name", "").strip()
    is_staged_recipes = recipe_dirname != "recipe"

    # 1: Check that the recipe does not exist in conda-forge or bioconda
    if is_staged_recipes and recipe_name:
        cf = gh.get_user(os.getenv("GH_ORG", "conda-forge"))
        try:
            for name in set(
                [
                    recipe_name,
                    recipe_name.replace("-", "_"),
                    recipe_name.replace("_", "-"),
                ]
            ):
                if cf.get_repo("{}-feedstock".format(name)):
                    existing_recipe_name = name
                    feedstock_exists = True
                    break
            else:
                feedstock_exists = False
        except github.UnknownObjectException as e:
            feedstock_exists = False

        if feedstock_exists and existing_recipe_name == recipe_name:
            lints.append("Feedstock with the same name exists in conda-forge.")
        elif feedstock_exists:
            hints.append(
                "Feedstock with the name {} exists in conda-forge. Is it the same as this package ({})?".format(
                    existing_recipe_name, recipe_name,
                )
            )

        bio = gh.get_user("bioconda").get_repo("bioconda-recipes")
        try:
            bio.get_dir_contents("recipes/{}".format(recipe_name))
        except github.UnknownObjectException as e:
            pass
        else:
            hints.append(
                "Recipe with the same name exists in bioconda: "
                "please discuss with @conda-forge/bioconda-recipes."
            )

    # 2: Check that the recipe maintainers exists:
    maintainers = extra_section.get("recipe-maintainers", [])
    for maintainer in maintainers:
        if "/" in maintainer:
            # It's a team. Checking for existence is expensive. Skip for now
            continue
        try:
            gh.get_user(maintainer)
        except github.UnknownObjectException as e:
            lints.append(
                'Recipe maintainer "{}" does not exist'.format(maintainer)
            )

    # 3: if the recipe dir is inside the example dir
    if recipe_dir is not None and "recipes/example/" in recipe_dir:
        lints.append(
            "Please move the recipe out of the example dir and "
            "into its own dir."
        )


def is_selector_line(line):
    # Using the same pattern defined in conda-build (metadata.py),
    # we identify selectors.
    line = line.rstrip()
    if line.lstrip().startswith("#"):
        # Don't bother with comment only lines
        return False
    m = sel_pat.match(line)
    if m:
        m.group(3)
        return True
    return False


def is_jinja_line(line):
    line = line.rstrip()
    m = jinja_pat.match(line)
    if m:
        return True
    return False


def selector_lines(lines):
    for i, line in enumerate(lines):
        if is_selector_line(line):
            yield line, i


def jinja_lines(lines):
    for i, line in enumerate(lines):
        if is_jinja_line(line):
            yield line, i


def main(recipe_dir, conda_forge=False, return_hints=False):
    recipe_dir = os.path.abspath(recipe_dir)
    recipe_meta = os.path.join(recipe_dir, "meta.yaml")
    if not os.path.exists(recipe_dir):
        raise IOError("Feedstock has no recipe/meta.yaml.")

    with io.open(recipe_meta, "rt") as fh:
        content = render_meta_yaml("".join(fh))
        meta = get_yaml().load(content)
    results, hints = lintify(meta, recipe_dir, conda_forge)
    if return_hints:
        return results, hints
    else:
        return results
