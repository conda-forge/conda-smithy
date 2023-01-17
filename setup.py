#!/usr/bin/env python
from setuptools import setup


def main():
    skw = dict(
        name="conda-smithy",
        description="A package to create repositories for conda recipes, and automate "
        "their building with CI tools on Linux, OSX and Windows.",
        author="Phil Elson",
        author_email="pelson.pub@gmail.com",
        url="https://github.com/conda-forge/conda-smithy",
        entry_points=dict(
            console_scripts=[
                "feedstocks = conda_smithy.feedstocks:main",
                "conda-smithy = conda_smithy.cli:main",
            ]
        ),
        include_package_data=True,
        packages=["conda_smithy"],
        # As conda-smithy has resources as part of the codebase, it is
        # not zip-safe.
        zip_safe=False,
        use_scm_version=True,
        setup_requires=["setuptools_scm"],
    )
    setup(**skw)


if __name__ == "__main__":
    main()
