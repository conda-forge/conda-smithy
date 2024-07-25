#!/usr/bin/env python
"""
Installs Miniconda with the latest version of Obvious-CI.

This script supports Python  3 (>=3.2+) and is
designed to run on OSX, Linux and Windows.

"""
import argparse
import os
import platform
import subprocess

try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve

MINICONDA_URL_TEMPLATE = (
    "https://repo.continuum.io/miniconda/Miniconda{major_py_version}-"
    "{miniconda_version}-{OS}-{arch}.{ext}"
)


def miniconda_url(
    target_system, target_arch, major_py_version, miniconda_version
):
    template_values = {"miniconda_version": miniconda_version}

    if target_arch == "x86":
        template_values["arch"] = "x86"
    elif target_arch == "x64":
        template_values["arch"] = "x86_64"
    else:
        raise ValueError("Unexpected target arch.")

    system_to_miniconda_os = {
        "Linux": "Linux",
        "Darwin": "MacOSX",
        "Windows": "Windows",
    }
    if target_system not in system_to_miniconda_os:
        raise ValueError(f"Unexpected system {target_system!r}.")
    template_values["OS"] = system_to_miniconda_os[target_system]

    miniconda_os_ext = {"Linux": "sh", "MacOSX": "sh", "Windows": "exe"}
    template_values["ext"] = miniconda_os_ext[template_values["OS"]]

    if major_py_version not in ["3"]:
        raise ValueError(
            f"Unexpected major Python version {major_py_version!r}."
        )
    template_values["major_py_version"] = major_py_version

    return MINICONDA_URL_TEMPLATE.format(**template_values)


def main(
    target_dir,
    target_arch,
    major_py_version,
    miniconda_version="latest",
    install_obvci=True,
):
    system = platform.system()
    URL = miniconda_url(
        system, target_arch, major_py_version, miniconda_version
    )
    basename = URL.rsplit("/", 1)[1]
    if system in ["Linux", "Darwin"]:
        cmd = ["bash", basename, "-b", "-p", target_dir]
        bin_dir = "bin"
    elif system in ["Windows"]:
        cmd = [
            "powershell",
            "Start-Process",
            "-FilePath",
            basename,
            "-ArgumentList",
            "/S,/D=" + target_dir,
            "-Wait",
        ]  # '-Passthru']
        bin_dir = "scripts"
    else:
        raise ValueError("Unsupported operating system.")

    if not os.path.exists(basename):
        print(f"Downloading from {URL}")
        urlretrieve(URL, basename)
    else:
        print(f"Using cached version of {URL}")

    # Install with powershell.
    if os.path.exists(target_dir):
        raise OSError("Installation directory already exists")
    subprocess.check_call(cmd)

    if not os.path.isdir(target_dir):
        raise RuntimeError("Failed to install miniconda :(")

    if install_obvci:
        conda_path = os.path.join(target_dir, bin_dir, "conda")
        subprocess.check_call(
            [
                conda_path,
                "install",
                "--yes",
                "--quiet",
                "-c",
                "pelson",
                "obvious-ci",
            ]
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""A script to download and install miniconda for Linux/OSX/Windows."""
    )
    parser.add_argument(
        "installation_directory",
        help="""Where miniconda should be installed.""",
    )
    parser.add_argument(
        "arch",
        help="""The target architecture of this build. (must be either "x86" or "x64").""",
        choices=["x86", "x64"],
    )
    parser.add_argument(
        "major_py_version",
        help="""The major Python version for the miniconda root env (may
                                                    still subsequently use another Python version).""",
        choices=["3"],
    )
    parser.add_argument(
        "--without-obvci",
        help="Disable the installation of Obvious-ci.",
        action="store_true",
    )
    parser.add_argument("--miniconda-version", default="latest")

    args = parser.parse_args()
    main(
        args.installation_directory,
        args.arch,
        args.major_py_version,
        miniconda_version=args.miniconda_version,
        install_obvci=not args.without_obvci,
    )
