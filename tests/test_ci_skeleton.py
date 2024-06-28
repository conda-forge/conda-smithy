from conda_smithy.ci_skeleton import generate

CONDA_FORGE_YML = """clone_depth: 0
recipe_dir: myrecipe
skip_render:
  - README.md
  - LICENSE.txt
  - .gitattributes
  - .gitignore
  - build-locally.py
  - LICENSE
  - .github/CONTRIBUTING.md
  - .github/ISSUE_TEMPLATE.md
  - .github/PULL_REQUEST_TEMPLATE.md
  - .github/workflows"""

META_YAML = """{% set name = "my-package" %}
{% set version = environ.get('GIT_DESCRIBE_TAG', 'untagged')|string|replace('-','_') %}
{% set build_number = environ.get('GIT_DESCRIBE_NUMBER', '0') %}

package:
  name: {{ name|lower }}
  version: {{ version }}

source:
  git_url: {{ environ.get('FEEDSTOCK_ROOT', '..') }}

build:
  # Uncomment the following line if the package is pure Python and the recipe
  # is exactly the same for all platforms. It is okay if the dependencies are
  # not built for all platforms/versions, although selectors are still not allowed.
  # See https://conda-forge.org/docs/maintainer/knowledge_base.html#noarch-python
  # for more details.
  # noarch: python

  number: {{ build_number }}
  string: {{ [build_number, ('h' + PKG_HASH), environ.get('GIT_DESCRIBE_HASH', '')]|join('_') }}

  # If the installation is complex, or different between Unix and Windows,
  # use separate bld.bat and build.sh files instead of this key. By default,
  # the package will be built for the Python versions supported by conda-forge
  # and for all major OSs. Add the line "skip: True  # [py<35]" (for example)
  # to limit to Python 3.5 and newer, or "skip: True  # [not win]" to limit
  # to Windows.
  script: "{{ PYTHON }} -m pip install . -vv"

requirements:
  build:
    # If your project compiles code (such as a C extension) then add the required
    # compilers as separate entries here. Compilers are named 'c', 'cxx' and 'fortran'.
    - {{ compiler('c') }}
  host:
    - python
    - pip
  run:
    - python

test:
  # Some packages might need a `test/commands` key to check CLI.
  # List all the packages/modules that `run_test.py` imports.
  imports:
    - my_package
  # Run your test commands here
  commands:
    - my-package --help
    - pytest
  # declare any test-only requirements here
  requires:
    - pytest
  # copy over any needed test files here
  source_files:
    - tests/

# Uncomment and fill in my-package metadata
#about:
#  home: https://github.com/conda-forge/conda-smithy
#  license: BSD-3-Clause
#  license_family: BSD
#  license_file: LICENSE

# Uncomment the following if this will be on a forge
# Remove these lines if this is only be used for CI
#extra:
#  recipe-maintainers:
#    - BobaFett
#    - LisaSimpson"""

GITIGNORE = """# conda smithy ci-skeleton start
*.pyc
build_artifacts
# conda smithy ci-skeleton end
"""


def test_generate(tmpdir):
    generate(
        package_name="my-package",
        feedstock_directory=str(tmpdir),
        recipe_directory="myrecipe",
    )
    with open(tmpdir / "conda-forge.yml") as f:
        conda_forge_yml = f.read()
    assert conda_forge_yml == CONDA_FORGE_YML
    with open(tmpdir / "myrecipe" / "meta.yaml") as f:
        meta_yaml = f.read()
    assert meta_yaml == META_YAML
    with open(tmpdir / ".gitignore") as f:
        gitignore = f.read()
    assert gitignore == GITIGNORE
