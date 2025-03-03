import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from glob import glob
from typing import Any

from conda_smithy.linter import conda_recipe_v1_linter
from conda_smithy.linter.errors import HINT_NO_ARCH
from conda_smithy.linter.utils import (
    VALID_PYTHON_BUILD_BACKENDS,
    find_local_config_file,
    flatten_v1_if_else,
    get_all_test_requirements,
    is_selector_line,
)
from conda_smithy.utils import get_yaml


def hint_pip_usage(build_section, hints):
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


def hint_sources_should_not_mention_pypi_io_but_pypi_org(
    sources_section: list[dict[str, Any]], hints: list[str]
):
    """
    Grayskull and conda-forge default recipe used to have pypi.io as a default,
    but cannonical url is PyPI.org.

    See https://github.com/conda-forge/staged-recipes/pull/27946
    """
    for source_section in sources_section:
        source = source_section.get("url", "") or ""
        sources = [source] if isinstance(source, str) else source
        if any(s.startswith("https://pypi.io/") for s in sources):
            hints.append(
                "PyPI default URL is now pypi.org, and not pypi.io."
                " You may want to update the default source url."
            )


def hint_suggest_noarch(
    noarch_value,
    build_reqs,
    raw_requirements_section,
    is_staged_recipes,
    conda_forge,
    recipe_fname,
    hints,
    recipe_version: int = 0,
):
    if (
        noarch_value is None
        and build_reqs
        and not any(["_compiler_stub" in b for b in build_reqs])
        and ("pip" in build_reqs)
        and (is_staged_recipes or not conda_forge)
    ):
        if recipe_version == 1:
            conda_recipe_v1_linter.hint_noarch_usage(
                build_reqs, raw_requirements_section, hints
            )
        else:
            with open(recipe_fname, encoding="utf-8") as fh:
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
                    hints.append(HINT_NO_ARCH)


def hint_shellcheck_usage(recipe_dir, hints):
    shellcheck_enabled = False
    shell_scripts = []
    if recipe_dir:
        shell_scripts = glob(os.path.join(recipe_dir, "*.sh"))
        forge_yaml = find_local_config_file(recipe_dir, "conda-forge.yml")
        if shell_scripts and forge_yaml:
            with open(forge_yaml, encoding="utf-8") as fh:
                code = get_yaml().load(fh)
                shellcheck_enabled = code.get("shellcheck", {}).get(
                    "enabled", shellcheck_enabled
                )

        if shellcheck_enabled and shutil.which("shellcheck") and shell_scripts:
            max_shellcheck_lines = 50
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
                if len(findings) > max_shellcheck_lines:
                    hints.append(
                        "Output restricted, there are '%s' more lines."
                        % (len(findings) - max_shellcheck_lines)
                    )
            elif p.returncode != 0:
                # Something went wrong.
                hints.append(
                    "There have been errors while scanning with shellcheck."
                )


def hint_check_spdx(about_section, hints):
    import license_expression

    license = about_section.get("license", "")
    licensing = license_expression.Licensing()
    parsed_exceptions = []
    try:
        parsed_licenses = []
        parsed_licenses_with_exception = licensing.license_symbols(
            license.strip(), decompose=False
        )
        for li in parsed_licenses_with_exception:
            if isinstance(li, license_expression.LicenseWithExceptionSymbol):
                parsed_licenses.append(li.license_symbol.key)
                parsed_exceptions.append(li.exception_symbol.key)
            else:
                parsed_licenses.append(li.key)
    except license_expression.ExpressionError:
        parsed_licenses = [license]

    licenseref_regex = re.compile(r"^LicenseRef[a-zA-Z0-9\-.]*$")
    filtered_licenses = []
    for license in parsed_licenses:
        if not licenseref_regex.match(license):
            filtered_licenses.append(license)

    with open(
        os.path.join(os.path.dirname(__file__), "licenses.txt"),
        encoding="utf-8",
    ) as f:
        expected_licenses = f.readlines()
        expected_licenses = {li.strip() for li in expected_licenses}
    with open(
        os.path.join(os.path.dirname(__file__), "license_exceptions.txt"),
        encoding="utf-8",
    ) as f:
        expected_exceptions = f.readlines()
        expected_exceptions = {li.strip() for li in expected_exceptions}
    if set(filtered_licenses) - expected_licenses:
        hints.append(
            "License is not an SPDX identifier (or a custom LicenseRef) nor an SPDX license expression.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )
    if set(parsed_exceptions) - expected_exceptions:
        hints.append(
            "License exception is not an SPDX exception.\n\n"
            "Documentation on acceptable licenses can be found "
            "[here]( https://conda-forge.org/docs/maintainer/adding_pkgs.html#spdx-identifiers-and-expressions )."
        )


def hint_pip_no_build_backend(host_or_build_section, package_name, hints):
    # we do NOT exclude all build backends since some of them
    # need another backend to bootstrap
    # the list below are the ones that self-bootstrap without
    # another build backend
    if package_name in ["pdm-backend", "setuptools"]:
        return

    if host_or_build_section and any(
        req.split(" ")[0] == "pip" for req in host_or_build_section
    ):
        found_backend = False
        for backend in VALID_PYTHON_BUILD_BACKENDS:
            if any(
                req.split(" ")[0]
                in [
                    backend,
                    backend.replace("-", "_"),
                    backend.replace("_", "-"),
                ]
                for req in host_or_build_section
            ):
                found_backend = True
                break

        if not found_backend:
            hints.append(
                f"No valid build backend found for Python recipe for package `{package_name}` using `pip`. "
                "Python recipes using `pip` need to "
                "explicitly specify a build backend in the `host` section. "
                "If your recipe has built with only `pip` in the `host` section in the past, you likely should "
                "add `setuptools` to the `host` section of your recipe."
            )


def _hint_noarch_python_use_python_min_inner(
    host_reqs,
    run_reqs,
    test_reqs,
    noarch_value,
    recipe_version,
    output_name,
):
    hint = []

    if noarch_value == "python":
        if recipe_version == 1:
            host_reqs = flatten_v1_if_else(host_reqs)
            run_reqs = flatten_v1_if_else(run_reqs)
            test_reqs = flatten_v1_if_else(test_reqs)

        for section_name, syntax, report_syntax, reqs in [
            (
                "host",
                r"python\s+=?=?{{ python_min }}",
                "python {{ python_min }}",
                host_reqs,
            ),
            (
                "run",
                r"python\s+>={{ python_min }}",
                "python >={{ python_min }}",
                run_reqs,
            ),
            (
                "test.requires",
                r"python\s+=?=?{{ python_min }}",
                "python {{ python_min }}",
                test_reqs,
            ),
        ]:
            if recipe_version == 1:
                syntax = syntax.replace(
                    "{{ python_min }}", r"\${{ python_min }}"
                )
                report_syntax = report_syntax.replace(
                    "{{ python_min }}", "${{ python_min }}"
                )
                test_syntax = syntax
            else:
                test_syntax = syntax.replace("{{ python_min }}", "9999")

            for req in reqs:
                if (
                    req.strip().split()[0] == "python"
                    and req != "python"
                    and re.search(test_syntax, req)
                ):
                    break
            else:
                section_desc = (
                    f"`{output_name}` output" if output_name else "recipe"
                )
                hint.append(
                    f"\n   - For the `{section_name}` section of {section_desc}, you should usually use `{report_syntax}` "
                    f"for the `python` entry."
                )
    return hint


def hint_noarch_python_use_python_min(
    host_reqs,
    run_reqs,
    test_reqs,
    outputs_section,
    noarch_value,
    recipe_version,
    hints,
):
    hint = []

    if outputs_section:
        for output_num, output in enumerate(outputs_section):
            requirements = output.get("requirements", {})
            if isinstance(requirements, Mapping):
                output_host_reqs = requirements.get("host")
                output_run_reqs = requirements.get("run")
            else:
                output_host_reqs = None
                output_run_reqs = requirements

            hint.extend(
                _hint_noarch_python_use_python_min_inner(
                    output_host_reqs or [],
                    output_run_reqs or [],
                    get_all_test_requirements(output, [], recipe_version),
                    output.get("build", {}).get("noarch"),
                    recipe_version,
                    output.get("package", {}).get(
                        "name", f"<output {output_num}"
                    ),
                )
            )
    else:
        hint.extend(
            _hint_noarch_python_use_python_min_inner(
                host_reqs,
                run_reqs,
                test_reqs,
                noarch_value,
                recipe_version,
                None,
            )
        )

    if hint:
        hint = (
            (
                "`noarch: python` recipes should usually follow the syntax in "
                "our [documentation](https://conda-forge.org/docs/maintainer/knowledge_base/#noarch-python) "
                "for specifying the Python version."
            )
            + "".join(hint)
            + (
                "\n   - If the package requires a newer Python version than the currently supported minimum "
                "version on `conda-forge`, you can override the `python_min` variable by adding a "
                "Jinja2 `set` statement at the top of your recipe (or using an equivalent `context` "
                "variable for v1 recipes)."
            )
        )
        hints.append(hint)


def hint_space_separated_specs(
    requirements_section,
    test_section,
    outputs_section,
    hints,
):
    report = {}
    for req_type, reqs in {
        **requirements_section,
        "test": test_section.get("requires") or (),
    }.items():
        bad_specs = [
            req
            for req in (reqs or ())
            if not _ensure_spec_space_separated(req)
        ]
        if bad_specs:
            report.setdefault("top-level", {})[req_type] = bad_specs
    for i, output in enumerate(outputs_section):
        requirements_section = output.get("requirements") or {}
        if not hasattr(requirements_section, "items"):
            # not a dict, but a list (CB2 style)
            requirements_section = {"run": requirements_section}
        for req_type, reqs in {
            "build": requirements_section.get("build") or [],
            "host": requirements_section.get("host") or [],
            "run": requirements_section.get("run") or [],
            "test": output.get("test", {}).get("requires") or [],
        }.items():
            bad_specs = [
                req for req in reqs if not _ensure_spec_space_separated(req)
            ]
            if bad_specs:
                report.setdefault(output.get("name", f"output {i}"), {})[
                    req_type
                ] = bad_specs

    lines = []
    for output, requirements in report.items():
        lines.append(f"{output} output has some malformed specs:")
        for req_type, specs in requirements.items():
            specs = [f"`{spec}" for spec in specs]
            lines.append(f"- In section {req_type}: {', '.join(specs)}")
    if lines:
        lines.append(
            "Requirement spec fields should always be space-separated to avoid known issues in "
            "conda-build. For example, instead of `name =version=build`, use `name version.* "
            "build`."
        )
        hints.append("\n".join(lines))


def _ensure_spec_space_separated(spec: str) -> bool:
    from conda import CondaError
    from conda.models.match_spec import MatchSpec

    if "#" in spec:
        spec = spec.split("#")[0]
    spec = spec.strip()
    fields = spec.split(" ")
    try:
        match_spec = MatchSpec(spec)
    except CondaError:
        return False

    if match_spec.strictness == len(fields):
        # strictness is a value between 1 and 3:
        # 1 = name only
        # 2 = name and version
        # 3 = name, version and build.
        return True
    return False
