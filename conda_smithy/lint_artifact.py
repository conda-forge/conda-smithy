from __future__ import annotations

import json
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING

from conda_package_streaming.package_streaming import stream_conda_info

if TYPE_CHECKING:
    from typing import Any


def get_paths_json(artifact: str | Path) -> dict[str, Any]:
    for tarfile, tarinfo in stream_conda_info(artifact):
        if tarinfo.name == "info/paths.json":
            return json.load(tarfile.extractfile(tarinfo))
    raise ValueError(f"Artifact '{artifact}' does not contain 'info/paths.json'")


def get_index_json(artifact: str | Path) -> dict[str, Any]:
    for tarfile, tarinfo in stream_conda_info(artifact):
        if tarinfo.name == "info/index.json":
            return json.load(tarfile.extractfile(tarinfo))
    raise ValueError(f"Artifact '{artifact}' does not contain 'info/index.json'")


def check_path_patterns(
    paths: list[str],
    index: dict[str, Any] | None = None,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    index = index or {}

    #: These will result in a lint if the path DOES NOT match
    allowed: list[str] = [
        "bin/*",
        "etc/*",
        "fonts/*",
        "include/*",
        "lib/*",
        "libexec/*",
        "Menu/*",  # menuinst location
        "share/*",
        "var/*",
    ]
    #: These will result in a hint if the path DOES match
    warned: dict[str, list[str]] = {
        "Place man and doc pages under share/man/ or share/doc/": [
            "man/*",
            "doc/*",
        ],
        "Place binaries under bin/, not sbin/": [
            "sbin/*",
        ],
        "Place fonts under share/fonts/, not fonts/": [
            "fonts/*",
        ],
    }
    #: These will result in a lint if the path DOES match
    disallowed: dict[str, list[str]] = {
        "Can't populate a top-level `test(s)` Python package": [
            "lib/python*.*/site-packages/tests?/*",
            "Lib/site-packages/tests?/*",
            "site-packages/tests?/*",
        ]
    }

    # Now the exceptions

    # Packages targeting Windows may have these special locations
    if index.get("subdir", "").startswith("win-") or any(
        dep.startswith("__win") for dep in index.get("depends", ())
    ):
        allowed.extend(
            [
                "Scripts/*",
                "Library/*",
                "Lib/*",
            ]
        )
    if index.get("noarch") == "python":
        allowed.append("site-packages/*")
    if index.get("name") in ("conda", "mamba"):
        allowed.append("condabin/*")
        allowed.append("shell/*")
    if index.get("name") in ("ca-certificates", "openssl"):
        allowed.append("ssl/*")

    allowed_patterns = ", ".join(f"`{pattern}`" for pattern in allowed)
    outside_allowed_msg = f"Found paths outside expected top-level trees ({allowed_patterns})"
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}
    for path in paths:
        received_error, received_warning = False, False
        if "/" not in path:
            # top-level file, skip
            continue
        for message, rules in disallowed.items():
            for rule in rules:
                if fnmatchcase(path, rule):
                    errors.setdefault(message, []).append(path)
                    received_error = True
        for message, rules in warned.items():
            for rule in rules:
                if fnmatchcase(path, rule):
                    warnings.setdefault(message, []).append(path)
                    received_warning = True
        if received_error or received_warning:
            continue  # avoid duplicate reports with the general deny list
        if not any(fnmatchcase(path, rule) for rule in allowed):
            errors.setdefault(outside_allowed_msg, []).append(path)

    return errors, warnings


def format_errors_warnings(
    errors: dict[str, list[str]],
    warnings: dict[str, list[str]],
    lints: list[str],
    hints: list[str],
) -> None:
    for message, paths in errors.items():
        joined_lines = "\n  ".join(sorted(dict.fromkeys(paths)))
        lints.append(
            f"- ❌ {message}:\n  ```text\n  {joined_lines}\n  ```"
        )
    for message, paths in warnings.items():
        joined_lines = "\n  ".join(sorted(dict.fromkeys(paths)))
        hints.append(
            f"- ℹ️ {message}:\n  ```text\n  {joined_lines}\n  ```"
        )


def main(artifact: str | Path) -> tuple[list[str], list[str]]:
    paths = [item["_path"] for item in get_paths_json(artifact)["paths"]]
    if not paths:
        return [], []

    lints: list[str] = []
    hints: list[str] = []

    errors, warnings = check_path_patterns(
        paths=paths,
        index=get_index_json(artifact),
    )
    format_errors_warnings(errors, warnings, lints, hints)

    return lints, hints


if __name__ == "__main__":
    import sys

    if not sys.argv[1:]:
        sys.exit("Must provide at least one artifact path!")
    exit_code = 0
    for artifact in sys.argv[1:]:
        lints, hints = main(artifact)
        if lints or hints:
            print("-" * len(artifact))
            print(artifact)
            print("-" * len(artifact))
            print("\n".join(lints))
            print("\n".join(hints))
            exit_code = 1
    sys.exit(exit_code)
