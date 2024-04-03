import copy
import fnmatch
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
from glob import glob
from pathlib import Path
from typing import Optional, Dict, Iterable, Tuple, List, TypeVar

from conda.models.version import VersionOrder
from conda_build.metadata import (
    FIELDS as cbfields,
)

from conda_smithy import linters_meta_yaml
from conda_smithy.linters_forge_yml import (
    FORGE_YAML_LINTERS,
)
from conda_smithy.linters_meta_yaml import (
    MetaYamlLintExtras,
    get_section,
    is_selector_line,
)
from conda_smithy.linting_types import LintsHints, Linter
from .utils import render_meta_yaml, get_yaml

FIELDS = copy.deepcopy(cbfields)

# Just in case 'extra' moves into conda_build
if "extra" not in FIELDS.keys():
    FIELDS["extra"] = {}

FIELDS["extra"]["recipe-maintainers"] = ()
FIELDS["extra"]["feedstock-name"] = ""

REQUIREMENTS_ORDER = ["build", "host", "run"]

jinja_pat = re.compile(r"\s*\{%\s*(set)\s+[^\s]+\s*=\s*[^\s]+\s*%\}")
JINJA_VAR_PAT = re.compile(r"{{(.*?)}}")

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


def find_local_config_file(recipe_dir, filename):
    # support
    # 1. feedstocks
    # 2. staged-recipes with custom conda-forge.yaml in recipe
    # 3. staged-recipes
    found_filesname = (
        glob(os.path.join(recipe_dir, filename))
        or glob(os.path.join(recipe_dir, "..", filename))
        or glob(os.path.join(recipe_dir, "..", "..", filename))
    )

    return found_filesname[0] if found_filesname else None


def _lint(
    contents: Dict, linters: Iterable[Linter[T]], lint_extras: T = None
) -> LintsHints:
    """
    Lint the contents of a file.
    :param contents: the contents of the file to lint
    :param linters: an iterable of linters to apply to the contents
    :param lint_extras: static extra data to pass to the linters
    :returns: a LintsHints object, containing lints and hints
    """
    results = LintsHints()

    for linter in linters:
        results += linter(contents, lint_extras)

    return results


def read_forge_yaml(recipe_dir: Path) -> dict:
    """
    Read the conda-forge.yml file, relative to the recipe_dir.
    :returns: a dict representing the conda-forge.yml file
    :raises FileNotFoundError: if no conda-forge.yml file is found
    :raises ValueError: if the conda-forge.yml file does not represent a dict
    """

    forge_yaml_candidates = [
        recipe_dir / ".." / "conda-forge.yml",
        recipe_dir / "conda-forge.yml",
        recipe_dir / ".." / ".." / "conda-forge.yml",
    ]

    for file in forge_yaml_candidates:
        try:
            forge_yaml = get_yaml().load(file)
            if isinstance(forge_yaml, dict):
                return forge_yaml

            raise ValueError(
                f"YAML file {file.resolve()} does not represent a dict"
            )
        except FileNotFoundError:
            continue
    else:
        raise FileNotFoundError(
            f"No conda-forge.yml file found in recipe directory {recipe_dir.resolve()}"
        )


def lint_forge_yaml(recipe_dir: Path) -> LintsHints:
    """
    Lint the conda-forge.yml file, relative to the recipe_dir.
    :returns: a LintsHints object, containing lints and hints
    """
    additional_lints = LintsHints()
    yaml: dict

    try:
        yaml = read_forge_yaml(recipe_dir)
    except ValueError as e:
        return LintsHints(lints=[str(e)])
    except FileNotFoundError:
        additional_lints += LintsHints(
            hints=[
                "No conda-forge.yml file found. This is treated as an empty config mapping."
            ]
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


def lint_meta_yaml(meta_yaml: dict) -> LintsHints:
    """
    Lint the meta.yaml file, relative to the recipe_dir.
    :returns: a LintsHints object, containing lints and hints
    """
    pass


def lintify_meta_yaml(
    meta, recipe_dir=None, conda_forge=False
) -> Tuple[List[str], List[str]]:
    """
    Lint the meta.yaml file, relative to the recipe_dir.
    :returns: a tuple (lints, hints)
    """
    lints = []
    hints = []
    major_sections = list(meta.keys())

    # If the recipe_dir exists (no guarantee within this function) , we can
    # find the meta.yaml within it.
    meta_fname = os.path.join(recipe_dir or "", "meta.yaml")

    build_section = get_section(meta, "build")
    requirements_section = get_section(meta, "requirements")
    about_section = get_section(meta, "about")
    package_section = get_section(meta, "package")
    outputs_section = get_section(meta, "outputs")

    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else "recipe"
    is_staged_recipes = recipe_dirname != "recipe"

    for section in unexpected_sections:
        major_sections.remove(section)

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
        for subsection in get_section(meta, section):
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
    # 17: Validate noarch
    noarch_value = build_section.get("noarch")
    if noarch_value is not None:
        valid_noarch_values = ["python", "generic"]
        if noarch_value not in valid_noarch_values:
            valid_noarch_str = "`, `".join(valid_noarch_values)
            lints.append(
                "Invalid `noarch` value `{}`. Should be one of `{}`.".format(
                    noarch_value, valid_noarch_str
                )
            )

    if recipe_dir:
        conda_build_config_filename = find_local_config_file(
            recipe_dir, "conda_build_config.yaml"
        )

        if conda_build_config_filename:
            with open(conda_build_config_filename, "r") as fh:
                conda_build_config_keys = set(get_yaml().load(fh).keys())
        else:
            conda_build_config_keys = set()

        forge_yaml_filename = find_local_config_file(
            recipe_dir, "conda-forge.yml"
        )

        if forge_yaml_filename:
            with open(forge_yaml_filename, "r") as fh:
                forge_yaml = get_yaml().load(fh)
        else:
            forge_yaml = {}
    else:
        conda_build_config_keys = set()
        forge_yaml = {}

    # 18: noarch doesn't work with selectors for runtime dependencies
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

    # 19: check version
    if package_section.get("version") is not None:
        ver = str(package_section.get("version"))
        try:
            VersionOrder(ver)
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

    # 25: require a lower bound on python version
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

    # 26: pin_subpackage is for subpackages and pin_compatible is for
    # non-subpackages of the recipe. Contact @carterbox for troubleshooting
    # this lint.
    subpackage_names = []
    for out in outputs_section:
        if "name" in out:
            subpackage_names.append(out["name"])  # explicit
    if "name" in package_section:
        subpackage_names.append(package_section["name"])  # implicit

    def check_pins(pinning_section):
        if pinning_section is None:
            return
        for pin in fnmatch.filter(pinning_section, "compatible_pin*"):
            if pin.split()[1] in subpackage_names:
                lints.append(
                    "pin_subpackage should be used instead of"
                    f" pin_compatible for `{pin.split()[1]}`"
                    " because it is one of the known outputs of this recipe:"
                    f" {subpackage_names}."
                )
        for pin in fnmatch.filter(pinning_section, "subpackage_pin*"):
            if pin.split()[1] not in subpackage_names:
                lints.append(
                    "pin_compatible should be used instead of"
                    f" pin_subpackage for `{pin.split()[1]}`"
                    " because it is not a known output of this recipe:"
                    f" {subpackage_names}."
                )

    def check_pins_build_and_requirements(top_level):
        if "build" in top_level and "run_exports" in top_level["build"]:
            check_pins(top_level["build"]["run_exports"])
        if "requirements" in top_level and "run" in top_level["requirements"]:
            check_pins(top_level["requirements"]["run"])
        if "requirements" in top_level and "host" in top_level["requirements"]:
            check_pins(top_level["requirements"]["host"])

    check_pins_build_and_requirements(meta)
    for out in outputs_section:
        check_pins_build_and_requirements(out)

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

    # 3: suggest fixing all recipe/*.sh shellcheck findings
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

    return lints, hints


def is_jinja_line(line):
    line = line.rstrip()
    m = jinja_pat.match(line)
    if m:
        return True
    return False


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

    results, hints = lintify_meta_yaml(meta, recipe_dir, conda_forge)
    forge_yaml_results = lint_forge_yaml(recipe_dir=Path(recipe_dir))

    results.extend(forge_yaml_results.lints)
    hints.extend(forge_yaml_results.hints)

    if return_hints:
        return results, hints
    else:
        return results


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
