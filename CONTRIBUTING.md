# Developing conda-smithy

## Set up Development Environment

To install conda-smithy from source:

* Install `conda`, e.g., via [Miniforge](https://conda-forge.org/download/).
* Fork and clone this repository: `git clone https://github.com/YOUR-USERNAME/conda-smithy.git`. Change to it: `cd conda-smithy`.
* Create a new conda environment with all requirements based on [environment.yml](environment.yml): `conda env create`.
* Activate the environment: `conda activate conda-smithy`.
  * Alternatively: Run `conda install -n base conda-spawn` and `conda spawn conda-smithy`
* Install conda-smithy: `pip install --no-deps --editable .`

To run all tests:

```sh
$ pytest
```

To run all code checks:

```sh
# staged changes
$ pre-commit run
# all files
$ pre-commit run --all-files
```

## Releasing conda-smithy

Before making a release, consult `@conda-forge/core` and wait some time for objections.

To release a new version of conda-smithy, you can use the
[rever](https://regro.github.io/rever-docs/index.html) release management tool.
Run `rever` in the root repo directory with the version number you want to release.
For example,

```sh
$ rever 0.1.2
```
