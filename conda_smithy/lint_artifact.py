from __future__ import annotations

import json
from fnmatch import fnmatch
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
    lints: list[str],
    hints: list[str],
    name: str,
    paths: list[str],
    subdir: str,
    noarch_python: bool = False,
) -> None:
    #: These will result in a lint if the path DOES NOT match
    outside_allowed_msg = "These files were found outside allowed locations"
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
    if subdir.startswith == "win-":
        allowed.extend(
            [
                "Scripts/*",
                "Library/*",
                "Lib/*",
            ]
        )
    if noarch_python:
        allowed.append("site-packages/*")
    if name in ("conda", "mamba"):
        allowed.append("condabin/*")
        allowed.append("shell/*")
    if name in ("ca-certificates", "openssl"):
        allowed.append("ssl/*")

    message = "Path outside expected top-level tree"
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}
    for path in paths:
        if "/" not in path:
            # top-level file, skip
            continue
        errored, received_warning = False, False
        for message, rules in disallowed.items():
            for rule in rules:
                if fnmatch(path, rule):
                    errors.setdefault(message, []).append(path)
                    errored = True
                    break
        if errored:
            continue
        for message, rules in warned.items():
            for rule in rules:
                if fnmatch(path, rule):
                    warnings.setdefault(message, []).append(path)
                    received_warning = True
                    break
        if received_warning:
            continue
        if not any(fnmatch(path, rule) for rule in allowed):
            errors.setdefault(outside_allowed_msg, []).append(path)

    for message, paths in errors.items():
        joined_lines = "\n  ".join(sorted(dict.fromkeys(paths)))
        lints.append(
            # noqa (keep formatting this way for clarity)
            f"- ❌ {message}:\n"
            "  ```text\n"
            f"  {joined_lines}\n"
            "  ```"
        )
    for message, paths in warnings.items():
        joined_lines = "\n  ".join(sorted(dict.fromkeys(paths)))
        hints.append(
            # noqa (keep formatting this way for clarity)
            f"- ℹ️ {message}:\n"
            "  ```text\n"
            f"  {joined_lines}\n"
            "  ```"
        )


def main(artifact: str | Path) -> tuple[list[str], list[str]]:
    paths = [item["_path"] for item in get_paths_json(artifact)["paths"]]
    if not paths:
        return [], []

    index_data = get_index_json(artifact)
    lints: list[str] = []
    hints: list[str] = []

    check_path_patterns(
        lints,
        hints,
        name=index_data["name"],
        paths=paths,
        subdir=index_data["subdir"],
        noarch_python=index_data.get("noarch") == "python",
    )

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
