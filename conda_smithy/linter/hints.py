from glob import glob
import io
import os
import re
import shutil
import subprocess
import sys

from conda_smithy.linter.utils import find_local_config_file, is_selector_line
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


def hint_suggest_noarch(
    noarch_value, build_reqs, is_staged_recipes, conda_forge, meta_fname, hints
):
    if (
        noarch_value is None
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


def hint_shellcheck_usage(recipe_dir, hints):
    shellcheck_enabled = False
    shell_scripts = []
    if recipe_dir:
        shell_scripts = glob(os.path.join(recipe_dir, "*.sh"))
        forge_yaml = find_local_config_file(recipe_dir, "conda-forge.yml")
        if shell_scripts and forge_yaml:
            with open(forge_yaml, "r") as fh:
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
        for l in parsed_licenses_with_exception:
            if isinstance(l, license_expression.LicenseWithExceptionSymbol):
                parsed_licenses.append(l.license_symbol.key)
                parsed_exceptions.append(l.exception_symbol.key)
            else:
                parsed_licenses.append(l.key)
    except license_expression.ExpressionError:
        parsed_licenses = [license]

    licenseref_regex = re.compile(r"^LicenseRef[a-zA-Z0-9\-.]*$")
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
