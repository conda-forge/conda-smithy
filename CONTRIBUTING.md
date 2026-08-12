# Developing conda-smithy

## Set up Development Environment

To install conda-smithy from source:

* Install `conda`
* Fork and clone this repository: `git clone https://github.com/YOUR-USERNAME/conda-smithy.git`. Change to it: `cd conda-smithy`.
* Create a new conda environment with all requirements based on [environment.yml](environment.yml): `conda env create -f environment.yml`.
* Activate the environment: `conda activate conda-smithy`.
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

To run pyrefly code checks:

```sh
$ pyrefly check --python-interpreter-path $(which python) --output-format min-text --count-errors=1 --search-path .
```

If you encounter pyrefly issues that you don't agree with, feel free to add a `# pyrefly: ignore[<error-type>]` comment to that line.
An ignored `pyrefly` error is insufficient reason to block the merge of a pull request.
