from collections.abc import Sequence
import re

import fnmatch
import io
import itertools
import os


from typing import Any, Optional

from ruamel.yaml import CommentedSeq


from conda_smithy.linter.utils import (
    FIELDS,
    JINJA_VAR_PAT,
    NEEDED_FAMILIES,
    REQUIREMENTS_ORDER,
    TEST_FILES,
    TEST_KEYS,
    is_selector_line,
    jinja_lines,
    EXPECTED_SECTION_ORDER,
    get_section,
    selector_lines,
)
from conda_smithy.utils import get_yaml

from conda_smithy import rattler_linter


from conda.models.version import VersionOrder

from rattler_build_conda_compat.loader import parse_recipe_config_file


def lint_section_order(major_sections, lints, is_rattler_build: bool = False):
    if not is_rattler_build:
        section_order_sorted = sorted(
            major_sections, key=EXPECTED_SECTION_ORDER.index
        )
    else:
        section_order_sorted = (
            rattler_linter.EXPECTED_MUTIPLE_OUTPUT_SECTION_ORDER
            if "outputs" in major_sections
            else rattler_linter.EXPECTED_SINGLE_OUTPUT_SECTION_ORDER
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


def lint_about_contents(about_section, lints, is_rattler_build: bool = False):
    expected_section = [
        "homepage" if is_rattler_build else "home",
        "license",
        "summary",
    ]
    for about_item in expected_section:
        # if the section doesn't exist, or is just empty, lint it.
        if not about_section.get(about_item, ""):
            lints.append(
                "The {} item is expected in the about section."
                "".format(about_item)
            )


def lint_recipe_maintainers(extra_section, lints):
    if not extra_section.get("recipe-maintainers", []):
        lints.append(
            "The recipe could do with some maintainers listed in "
            "the `extra/recipe-maintainers` section."
        )
    if not (
        isinstance(extra_section.get("recipe-maintainers", []), Sequence)
        and not isinstance(extra_section.get("recipe-maintainers", []), str)
    ):
        lints.append("Recipe maintainers should be a json list.")


def lint_recipe_have_tests(
    recipe_dir,
    test_section,
    outputs_section,
    lints,
    hints,
    is_rattler_build: bool = False,
):
    if is_rattler_build:
        rattler_linter.lint_recipe_tests(
            test_section, outputs_section, lints, hints
        )
        return

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
                    elif test_out.get("script", "").endswith((".bat", ".sh")):
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


def lint_license_cannot_be_unknown(about_section, lints):
    license = about_section.get("license", "").lower()
    if "unknown" == license.strip():
        lints.append("The recipe license cannot be unknown.")


def lint_selectors_should_be_in_tidy_form(recipe_fname, lints, hints):
    bad_selectors, bad_lines = [], []
    pyXY_selectors_lint, pyXY_lines_lint = [], []
    pyXY_selectors_hint, pyXY_lines_hint = [], []
    # Good selectors look like ".*\s\s#\s[...]"
    good_selectors_pat = re.compile(r"(.+?)\s{2,}#\s\[(.+)\](?(2).*)$")
    # Look out for py27, py35 selectors; we prefer py==35
    pyXY_selectors_pat = re.compile(r".+#\s*\[.*?(py\d{2,3}).*\]")
    if os.path.exists(recipe_fname):
        with io.open(recipe_fname, "rt") as fh:
            for selector_line, line_number in selector_lines(fh):
                if not good_selectors_pat.match(selector_line):
                    bad_selectors.append(selector_line)
                    bad_lines.append(line_number)
                pyXY_matches = pyXY_selectors_pat.match(selector_line)
                if pyXY_matches:
                    for pyXY in pyXY_matches.groups():
                        if int(pyXY[2:]) in (27, 34, 35, 36):
                            # py27, py35 and so on are ok up to py36 (included); only warn
                            pyXY_selectors_hint.append(selector_line)
                            pyXY_lines_hint.append(line_number)
                        else:
                            pyXY_selectors_lint.append(selector_line)
                            pyXY_lines_lint.append(line_number)
    if bad_selectors:
        lints.append(
            "Selectors are suggested to take a "
            "``<two spaces>#<one space>[<expression>]`` form."
            " See lines {}".format(bad_lines)
        )
    if pyXY_selectors_hint:
        hints.append(
            "Old-style Python selectors (py27, py34, py35, py36) are "
            "deprecated. Instead, consider using the int ``py``. For "
            "example: ``# [py>=36]``. See lines {}".format(pyXY_lines_hint)
        )
    if pyXY_selectors_lint:
        lints.append(
            "Old-style Python selectors (py27, py35, etc) are only available "
            "for Python 2.7, 3.4, 3.5, and 3.6. Please use explicit comparisons "
            "with the integer ``py``, e.g. ``# [py==37]`` or ``# [py>=37]``. "
            "See lines {}".format(pyXY_lines_lint)
        )


def lint_build_section_should_have_a_number(build_section, lints):
    if build_section.get("number", None) is None:
        lints.append("The recipe must have a `build/number` section.")


def lint_build_section_should_be_before_run(requirements_section, lints):
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


def lint_sources_should_have_hash(sources_section, lints):
    for source_section in sources_section:
        if "url" in source_section and not (
            {"sha1", "sha256", "md5"} & set(source_section.keys())
        ):
            lints.append(
                "When defining a source/url please add a sha256, sha1 "
                "or md5 checksum (sha256 preferably)."
            )


def lint_license_should_not_have_license(about_section, lints):
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


def lint_should_be_empty_line(meta_fname, lints):
    if os.path.exists(meta_fname):
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


def lint_license_family_should_be_valid(
    about_section, license, lints, is_rattler_build: bool
):
    if not is_rattler_build:
        license_family = about_section.get("license_family", license).lower()
        license_file = about_section.get("license_file", None)
        if not license_file and any(
            f for f in NEEDED_FAMILIES if f in license_family
        ):
            lints.append("license_file entry is missing, but is required.")
    else:
        license_file = about_section.get("license_file", None)
        if not license_file:
            lints.append("license_file entry is missing, but is required.")


def lint_recipe_name(
    package_section, context_section, lints, is_rattler_build: bool
):
    if is_rattler_build:
        rattler_linter.lint_package_name(
            package_section, context_section, lints
        )
    else:
        recipe_name = package_section.get("name", "").strip()
        if re.match(r"^[a-z0-9_\-.]+$", recipe_name) is None:
            lints.append(
                "Recipe name has invalid characters. only lowercase alpha, numeric, "
                "underscores, hyphens and dots allowed"
            )


def lint_usage_of_legacy_patterns(requirements_section, lints):
    build_reqs = requirements_section.get("build", None)
    if build_reqs and ("numpy x.x" in build_reqs):
        lints.append(
            "Using pinned numpy packages is a deprecated pattern.  Consider "
            "using the method outlined "
            "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#linking-numpy)."
        )


def lint_subheaders(major_sections, meta, lints):
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


def lint_noarch(noarch_value: Optional[str], lints):
    if noarch_value is not None:
        valid_noarch_values = ["python", "generic"]
        if noarch_value not in valid_noarch_values:
            valid_noarch_str = "`, `".join(valid_noarch_values)
            lints.append(
                "Invalid `noarch` value `{}`. Should be one of `{}`.".format(
                    noarch_value, valid_noarch_str
                )
            )


def lint_noarch_and_runtime_dependencies(
    meta,
    meta_fname,
    noarch_value,
    build_section,
    forge_yaml,
    conda_build_config_keys,
    lints,
    is_rattler_build: bool = False,
):
    if is_rattler_build:
        raw_requirements_section = meta.get("requirements", {})
        rattler_linter.lint_usage_of_selectors_for_noarch(
            noarch_value, build_section, raw_requirements_section, lints
        )
        return

    if noarch_value is not None and os.path.exists(meta_fname):
        noarch_platforms = len(forge_yaml.get("noarch_platforms", [])) > 1
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
                        "`noarch` packages can't have skips with selectors. If "
                        "the selectors are necessary, please remove "
                        "`noarch: {}`.".format(noarch_value)
                    )
                    break
                if in_runreqs:
                    if runreqs_spacing == line[: -len(line.lstrip())]:
                        in_runreqs = False
                        continue
                    if is_selector_line(
                        line,
                        allow_platforms=noarch_platforms,
                        allow_keys=conda_build_config_keys,
                    ):
                        lints.append(
                            "`noarch` packages can't have selectors. If "
                            "the selectors are necessary, please remove "
                            "`noarch: {}`.".format(noarch_value)
                        )
                        break


def lint_package_version(
    package_section, context_section, lints, is_rattler_build: bool = False
):
    if is_rattler_build:
        rattler_linter.lint_package_version(
            package_section, context_section, lints
        )
    else:
        if package_section.get("version") is not None:
            ver = str(package_section.get("version"))
            try:
                VersionOrder(ver)
            except Exception:
                lints.append(
                    "Package version {} doesn't match conda spec".format(ver)
                )


def lint_jinja_variables_definitions(meta_fname, lints):
    bad_jinja = []
    bad_lines = []
    # Good Jinja2 variable definitions look like "{% set .+ = .+ %}"
    good_jinja_pat = re.compile(r"\s*\{%\s(set)\s[^\s]+\s=\s[^\s]+\s%\}")
    if os.path.exists(meta_fname):
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


def lint_legacy_usage_of_compilers(build_reqs, lints):
    if build_reqs and ("toolchain" in build_reqs):
        lints.append(
            "Using toolchain directly in this manner is deprecated.  Consider "
            "using the compilers outlined "
            "[here](https://conda-forge.org/docs/maintainer/knowledge_base.html#compilers)."
        )


def lint_single_space_in_pinned_requirements(
    requirements_section, lints, is_rattler_build: bool = False
):
    for section, requirements in requirements_section.items():
        for requirement in requirements or []:
            if is_rattler_build:
                req = requirement
                symbol_to_check = "${{"
            else:
                req, _, _ = requirement.partition("#")
                symbol_to_check = "{{"

            if symbol_to_check in req:
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


def lint_non_noarch_builds(
    requirements_section, outputs_section, noarch_value, lints
):
    check_languages = ["python", "r-base"]
    host_reqs = requirements_section.get("host") or []
    run_reqs = requirements_section.get("run") or []
    for language in check_languages:
        if noarch_value is None and not outputs_section:
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


def lint_jinja_var_references(
    recipe_fname, hints, is_rattler_build: bool = False
):
    if os.path.exists(recipe_fname):
        bad_vars = []
        bad_lines = []
        jinja_pattern = (
            JINJA_VAR_PAT
            if not is_rattler_build
            else rattler_linter.JINJA_VAR_PAT
        )
        with io.open(recipe_fname, "rt") as fh:
            for i, line in enumerate(fh.readlines()):
                for m in jinja_pattern.finditer(line):
                    if m.group(1) is not None:
                        var = m.group(1)
                        if var != " %s " % var.strip():
                            bad_vars.append(m.group(1).strip())
                            bad_lines.append(i + 1)
        if bad_vars:
            hint_message = (
                "``{{<one space><variable name><one space>}}``"
                if not is_rattler_build
                else "``${{<one space><variable name><one space>}}``"
            )
            hints.append(
                "Jinja2 variable references are suggested to "
                f"take a {hint_message}"
                " form. See lines %s." % (bad_lines,)
            )


def lint_require_lower_bound_on_python_version(
    run_reqs, outputs_section, noarch_value, lints
):
    if noarch_value == "python" and not outputs_section:
        for req in run_reqs:
            if (req.strip().split()[0] == "python") and (req != "python"):
                break
        else:
            lints.append(
                "noarch: python recipes are required to have a lower bound "
                "on the python version. Typically this means putting "
                "`python >=3.6` in **both** `host` and `run` but you should check "
                "upstream for the package's Python compatibility."
            )


def lint_pin_subpackages(
    meta,
    outputs_section,
    package_section,
    lints,
    is_rattler_build: bool = False,
):
    subpackage_names = []
    for out in outputs_section:
        if "name" in out:
            subpackage_names.append(out["name"])  # explicit
    if "name" in package_section:
        subpackage_names.append(package_section["name"])  # implicit

    def check_pins(pinning_section):
        if pinning_section is None:
            return
        filter_pin = (
            "pin_compatible*" if is_rattler_build else "compatible_pin*"
        )
        for pin in fnmatch.filter(pinning_section, filter_pin):
            if pin.split()[1] in subpackage_names:
                lints.append(
                    "pin_subpackage should be used instead of"
                    f" pin_compatible for `{pin.split()[1]}`"
                    " because it is one of the known outputs of this recipe:"
                    f" {subpackage_names}."
                )
        filter_pin = (
            "pin_subpackage*" if is_rattler_build else "subpackage_pin*"
        )
        for pin in fnmatch.filter(pinning_section, filter_pin):
            if pin.split()[1] not in subpackage_names:
                lints.append(
                    "pin_compatible should be used instead of"
                    f" pin_subpackage for `{pin.split()[1]}`"
                    " because it is not a known output of this recipe:"
                    f" {subpackage_names}."
                )

    def check_pins_build_and_requirements(top_level):
        if not is_rattler_build:
            if "build" in top_level and "run_exports" in top_level["build"]:
                check_pins(top_level["build"]["run_exports"])
            if (
                "requirements" in top_level
                and "run" in top_level["requirements"]
            ):
                check_pins(top_level["requirements"]["run"])
            if (
                "requirements" in top_level
                and "host" in top_level["requirements"]
            ):
                check_pins(top_level["requirements"]["host"])
        else:
            if (
                "requirements" in top_level
                and "run_exports" in top_level["requirements"]
            ):
                if "strong" in top_level["requirements"]["run_exports"]:
                    check_pins(
                        top_level["requirements"]["run_exports"]["strong"]
                    )
                else:
                    check_pins(top_level["requirements"]["run_exports"])

    check_pins_build_and_requirements(meta)
    for out in outputs_section:
        check_pins_build_and_requirements(out)


def lint_check_usage_of_whls(meta_fname, noarch_value, lints, hints):
    pure_python_wheel_urls = []
    compiled_wheel_urls = []
    # We could iterate on `sources_section`, but that might miss platform specific selector lines
    # ... so raw meta.yaml and regex it is...
    pure_python_wheel_re = re.compile(r".*[:-]\s+(http.*-none-any\.whl)\s+.*")
    wheel_re = re.compile(r".*[:-]\s+(http.*\.whl)\s+.*")
    if os.path.exists(meta_fname):
        with open(meta_fname, "rt") as f:
            for line in f:
                if match := pure_python_wheel_re.search(line):
                    pure_python_wheel_urls.append(match.group(1))
                elif match := wheel_re.search(line):
                    compiled_wheel_urls.append(match.group(1))
        if compiled_wheel_urls:
            formatted_urls = ", ".join(
                [f"`{url}`" for url in compiled_wheel_urls]
            )
            lints.append(
                f"Detected compiled wheel(s) in source: {formatted_urls}. "
                "This is disallowed. All packages should be built from source except in "
                "rare and exceptional cases."
            )
        if pure_python_wheel_urls:
            formatted_urls = ", ".join(
                [f"`{url}`" for url in pure_python_wheel_urls]
            )
            if noarch_value == "python":  # this is ok, just hint
                hints.append(
                    f"Detected pure Python wheel(s) in source: {formatted_urls}. "
                    "This is generally ok for pure Python wheels and noarch=python "
                    "packages but it's preferred to use a source distribution (sdist) if possible."
                )
            else:
                lints.append(
                    f"Detected pure Python wheel(s) in source: {formatted_urls}. "
                    "This is discouraged. Please consider using a source distribution (sdist) instead."
                )


def lint_rust_licenses_are_bundled(
    build_reqs, lints, is_rattler_build: bool = False
):
    rust_compiler = (
        "{{ compiler('rust') }}"
        if not is_rattler_build
        else "${{ compiler('rust') }}"
    )
    if build_reqs and (rust_compiler in build_reqs):
        if "cargo-bundle-licenses" not in build_reqs:
            lints.append(
                "Rust packages must include the licenses of the Rust dependencies. "
                "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#rust"
            )


def lint_go_licenses_are_bundled(
    build_reqs, lints, is_rattler_build: bool = False
):
    go_compiler = (
        "{{ compiler('go') }}"
        if not is_rattler_build
        else "${{ compiler('go') }}"
    )
    if build_reqs and (go_compiler in build_reqs):
        if "go-licenses" not in build_reqs:
            lints.append(
                "Go packages must include the licenses of the Go dependencies. "
                "For more info, visit: https://conda-forge.org/docs/maintainer/adding_pkgs/#go"
            )


def lint_stdlib(
    meta,
    recipe_dir,
    requirements_section,
    conda_build_config_filename,
    lints,
    hints,
    is_rattler_build: bool = False,
):
    global_build_reqs = requirements_section.get("build") or []
    global_run_reqs = requirements_section.get("run") or []
    global_constraints = requirements_section.get("run_constrained") or []
    if not is_rattler_build:
        global_constraints = requirements_section.get("run_constrained") or []

    build_lint = (
        '`{{ stdlib("c") }}`'
        if not is_rattler_build
        else '`${{ stdlib("c") }}`'
    )

    stdlib_lint = (
        "This recipe is using a compiler, which now requires adding a build "
        f"dependence on {build_lint} as well. Note that this rule applies to "
        "each output of the recipe using a compiler. For further details, please "
        "see https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    if not is_rattler_build:
        pat_compiler_stub = re.compile(
            "(m2w64_)?(c|cxx|fortran|rust)_compiler_stub"
        )
    else:
        pat_compiler_stub = re.compile(r"^\${{ compiler\(")

    outputs = get_section(meta, "outputs", lints, is_rattler_build)
    output_reqs = [x.get("requirements", {}) for x in outputs]

    # deal with cb2 recipes (no build/host/run distinction)
    if not is_rattler_build:
        output_reqs = [
            {"host": x, "run": x} if isinstance(x, CommentedSeq) else x
            for x in output_reqs
        ]

    # collect output requirements
    output_build_reqs = [x.get("build", []) or [] for x in output_reqs]
    output_run_reqs = [x.get("run", []) or [] for x in output_reqs]
    if not is_rattler_build:
        output_contraints = [
            x.get("run_constrained", []) or [] for x in output_reqs
        ]

    # aggregate as necessary
    all_build_reqs = [global_build_reqs] + output_build_reqs
    all_build_reqs_flat = global_build_reqs
    all_run_reqs_flat = global_run_reqs
    if not is_rattler_build:
        all_contraints_flat = global_constraints
    [all_build_reqs_flat := all_build_reqs_flat + x for x in output_build_reqs]
    [all_run_reqs_flat := all_run_reqs_flat + x for x in output_run_reqs]
    if not is_rattler_build:
        [
            all_contraints_flat := all_contraints_flat + x
            for x in output_contraints
        ]

    # this check needs to be done per output --> use separate (unflattened) requirements
    for build_reqs in all_build_reqs:
        has_compiler = any(pat_compiler_stub.match(rq) for rq in build_reqs)
        stdlib_stub = "c_stdlib_stub" if not is_rattler_build else "${{ stdlib"
        if has_compiler and stdlib_stub not in build_reqs:
            if stdlib_lint not in lints:
                lints.append(stdlib_lint)

    sysroot_lint_build = (
        '`{{ stdlib("c") }}`'
        if not is_rattler_build
        else '`${{ stdlib("c") }}`'
    )

    sysroot_lint = (
        "You're setting a requirement on sysroot_linux-<arch> directly; this should "
        f"now be done by adding a build dependence on {sysroot_lint_build}, and "
        "overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for the "
        "respective platform as necessary. For further details, please see "
        "https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    pat_sysroot = re.compile(r"sysroot_linux.*")
    if any(pat_sysroot.match(req) for req in all_build_reqs_flat):
        if sysroot_lint not in lints:
            lints.append(sysroot_lint)

    osx_lint = (
        "You're setting a constraint on the `__osx` virtual package directly; this "
        'should now be done by adding a build dependence on `{{ stdlib("c") }}`, '
        "and overriding `c_stdlib_version` in `recipe/conda_build_config.yaml` for "
        "the respective platform as necessary. For further details, please see "
        "https://github.com/conda-forge/conda-forge.github.io/issues/2102."
    )
    if not is_rattler_build:
        to_check = all_run_reqs_flat + all_contraints_flat
    else:
        to_check = all_run_reqs_flat
    if any(req.startswith("__osx >") for req in to_check):
        if osx_lint not in lints:
            lints.append(osx_lint)

    # stdlib issues in CBC ( conda-build-config )
    cbc_osx = {}
    if not is_rattler_build:
        cbc_lines = []
        if conda_build_config_filename:
            with open(conda_build_config_filename, "r") as fh:
                cbc_lines = fh.readlines()
    elif is_rattler_build and recipe_dir:
        platform_namespace = {
            "unix": True,
            "osx": True,
            "linux": False,
            "win": False,
        }
        variants_path = os.path.join(recipe_dir, "variants.yaml")
        if os.path.exists(variants_path):
            cbc_osx = parse_recipe_config_file(
                variants_path, platform_namespace, allow_missing_selector=True
            )

    # filter on osx-relevant lines
    if not is_rattler_build:
        pat = re.compile(
            r"^([^:\#]*?)\s+\#\s\[.*(not\s(osx|unix)|(?<!not\s)(linux|win)).*\]\s*$"
        )
        # remove lines with selectors that don't apply to osx, i.e. if they contain
        # "not osx", "not unix", "linux" or "win"; this also removes trailing newlines.
        # the regex here doesn't handle `or`-conjunctions, but the important thing for
        # having a valid yaml after filtering below is that we avoid filtering lines with
        # a colon (`:`), meaning that all yaml keys "survive". As an example, keys like
        # c_stdlib_version can have `or`'d selectors, even if all values are arch-specific.
        cbc_lines_osx = [pat.sub("", x) for x in cbc_lines]
        cbc_content_osx = "\n".join(cbc_lines_osx)
        cbc_osx = get_yaml().load(cbc_content_osx) or {}
        # filter None values out of cbc_osx dict, can appear for example with
        # ```
        # c_stdlib_version:  # [unix]
        #   - 2.17           # [linux]
        #   # note lack of osx
        # ```

    cbc_osx = dict(filter(lambda item: item[1] is not None, cbc_osx.items()))

    def sort_osx(versions):
        # we need to have a known order for [x64, arm64]; in the absence of more
        # complicated regex processing, we assume that if there are two versions
        # being specified, the higher one is osx-arm64.
        if len(versions) == 2:
            if VersionOrder(str(versions[0])) > VersionOrder(str(versions[1])):
                versions = versions[::-1]
        return versions

    baseline_version = ["10.13", "11.0"]
    v_stdlib = sort_osx(cbc_osx.get("c_stdlib_version", baseline_version))
    macdt = sort_osx(cbc_osx.get("MACOSX_DEPLOYMENT_TARGET", baseline_version))
    sdk = sort_osx(cbc_osx.get("MACOSX_SDK_VERSION", baseline_version))

    if {"MACOSX_DEPLOYMENT_TARGET", "c_stdlib_version"} <= set(cbc_osx.keys()):
        # both specified, check that they match
        if len(v_stdlib) != len(macdt):
            # if lengths aren't matching, assume it's a legal combination
            # where one key is specified for less arches than the other and
            # let the rerender deal with the details
            pass
        else:
            mismatch_lint = (
                "Conflicting specification for minimum macOS deployment target!\n"
                "If your conda_build_config.yaml sets `MACOSX_DEPLOYMENT_TARGET`, "
                "please change the name of that key to `c_stdlib_version`!\n"
                "Continuing with `max(c_stdlib_version, MACOSX_DEPLOYMENT_TARGET)`."
                "Continuing with `max(c_stdlib_version, MACOSX_DEPLOYMENT_TARGET)`."
            )
            merged_dt = []
            for v_std, v_mdt in zip(v_stdlib, macdt):
                # versions with a single dot may have been read as floats
                v_std, v_mdt = str(v_std), str(v_mdt)
                if VersionOrder(v_std) != VersionOrder(v_mdt):
                    if mismatch_lint not in lints:
                        lints.append(mismatch_lint)
                merged_dt.append(
                    v_mdt
                    if VersionOrder(v_std) < VersionOrder(v_mdt)
                    else v_std
                )
            cbc_osx["merged"] = merged_dt
    elif "MACOSX_DEPLOYMENT_TARGET" in cbc_osx.keys():
        cbc_osx["merged"] = macdt
        # only MACOSX_DEPLOYMENT_TARGET, should be renamed
        deprecated_dt = (
            "In your conda_build_config.yaml, please change the name of "
            "`MACOSX_DEPLOYMENT_TARGET`, to `c_stdlib_version`!"
        )
        if deprecated_dt not in hints:
            lints.append(deprecated_dt)
    elif "c_stdlib_version" in cbc_osx.keys():
        cbc_osx["merged"] = v_stdlib
        # only warn if version is below baseline
        outdated_lint = (
            "You are setting `c_stdlib_version` below the current global baseline "
            "in conda-forge (10.13). If this is your intention, you also need to "
            "override `MACOSX_DEPLOYMENT_TARGET` (with the same value) locally."
        )
        if len(v_stdlib) == len(macdt):
            # if length matches, compare individually
            for v_std, v_mdt in zip(v_stdlib, macdt):
                if VersionOrder(str(v_std)) < VersionOrder(str(v_mdt)):
                    if outdated_lint not in lints:
                        lints.append(outdated_lint)
        elif len(v_stdlib) == 1:
            # if length doesn't match, only warn if a single stdlib version
            # is lower than _all_ baseline deployment targets
            if all(
                VersionOrder(str(v_stdlib[0])) < VersionOrder(str(v_mdt))
                for v_mdt in macdt
            ):
                if outdated_lint not in lints:
                    lints.append(outdated_lint)

    # warn if SDK is lower than merged v_stdlib/macdt
    merged_dt = cbc_osx.get("merged", baseline_version)
    sdk_lint = (
        "You are setting `MACOSX_SDK_VERSION` below `c_stdlib_version`, "
        "in conda_build_config.yaml which is not possible! Please ensure "
        "`MACOSX_SDK_VERSION` is at least `c_stdlib_version` "
        "(you can leave it out if it is equal).\n"
        "If you are not setting `c_stdlib_version` yourself, this means "
        "you are requesting a version below the current global baseline in "
        "conda-forge (10.13). If this is the intention, you also need to "
        "override `c_stdlib_version` and `MACOSX_DEPLOYMENT_TARGET` locally."
    )
    if len(sdk) == len(merged_dt):
        # if length matches, compare individually
        for v_sdk, v_mdt in zip(sdk, merged_dt):
            # versions with a single dot may have been read as floats
            v_sdk, v_mdt = str(v_sdk), str(v_mdt)
            if VersionOrder(v_sdk) < VersionOrder(v_mdt):
                if sdk_lint not in lints:
                    lints.append(sdk_lint)
    elif len(sdk) == 1:
        # if length doesn't match, only warn if a single SDK version
        # is lower than _all_ merged deployment targets
        if all(
            VersionOrder(str(sdk[0])) < VersionOrder(str(v_mdt))
            for v_mdt in merged_dt
        ):
            if sdk_lint not in lints:
                lints.append(sdk_lint)
