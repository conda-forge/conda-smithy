=======================
conda-smithy Change Log
=======================

.. current developments

v3.36.1
====================

**Added:**

* Enable Dependabot for Github Actions workflows and templates. (#1930)
* Lint / hint if a recipe uses Python wheels as its source. (#1935 via #1936)

**Changed:**

* Lint all outputs for required stdlib-fixes. (#1941)
* Make recommended changes to Travis CI template. (#1942)

**Fixed:**

* Avoid linter failing on more complicated selector patterns in `conda_build_config.yaml`. (#1939)

**Authors:**

* Matthew R. Becker
* Jaime Rodríguez-Guerra
* H. Vetinari
* Uwe L. Korn
* Mervin Fansler
* dependabot[bot]



v3.36.0
====================

**Added:**

* Added new lint for no ``.ci_support`` files which indicates no packages being built.

**Changed:**

* Provide linter hints if macOS quantities are misconfigured in `conda_build_config.yaml` (#1929)

**Fixed:**

* Ensure MACOSX_SDK_VERSION does not end up lower than `c_stdlib_version` in variant configs (#1927 via #1928)
* Only mark the toplevel LICENSE and README as generated files

**Authors:**

* Matthew R. Becker
* H. Vetinari
* Uwe L. Korn



v3.35.1
====================

**Removed:**

* ``automerge.yml`` workflow template no longer relies on ``actions/checkout``. (#1923)

**Fixed:**

* linter no longer mis-diagnoses constraint-less ``__osx`` as requiring change. (#1925)
* Fixed a bug where some keys in zips were not being rendered correctly into the ``.ci_support`` files
  under some hard-to-describe circumstances.
* Fixed source URL for rever releases.

**Authors:**

* Matthew R. Becker
* Jaime Rodríguez-Guerra
* H. Vetinari
* pre-commit-ci[bot]



v3.35.0
====================

**Changed:**

* Do not populate `c_stdlib{,_version}` in CI configs that don't need them (#1908)
* Added linter rules for providing hints about updating to new stdlib-functionality (#1909)
* Github Actions: Explicitly use ``macos-13`` for ``osx-64`` runners. (#1913)
* Github Actions: Bump to ``setup-miniconda@v3`` on Windows builds. (#1913)
* Azure Pipelines: bump default macOS runners ``vmImage`` value to ``macos-12``. (#1914)

**Authors:**

* Jaime Rodríguez-Guerra
* H. Vetinari



v3.34.1
====================

**Removed:**

* ``false`` is no longer a valid value for ``bot.inspection`` in the ``conda-forge.yml`` file. Use ``disabled`` instead.

**Fixed:**

* ``object`` is no longer an explicit base class of ``Subcommand`` (Python 3 class style)
* replace ``logger.warn`` (deprecated) with ``logger.warning``
* typo: `Usage` in ``update_conda_forge_config``
* Unexpected top-level ``conda-forge.yml`` keys should no longer fail with a traceback.

**Security:**

* Use sandboxed jinja2 environments. (#1902)

**Authors:**

* Matthew R. Becker
* pre-commit-ci[bot]
* Nicholas Bollweg
* Yannik Tausch



v3.34.0
====================

**Added:**

* ``disabled`` is now a supported option for ``bot.inspection`` in the ``conda-forge.yml`` file (previously: ``false``)
* Add ``github_actions.free_disk_space`` to schema ( #1882 )

**Changed:**

* Do not raise on ``conda-forge.yml`` validation errors during rerender. A warning will be printed instead. (#1879 via #1885)
* Adjust how the linter processes ``conda-forge.yml`` validation issues for prettier Markdown rendering. (#1860 via #1886)
* Ensure new ``{{ stdlib("c") }}`` correctly populates CI config. (#1840 via #1888)
* Ensure we populate MACOSX_DEPLOYMENT_TARGET for use in conda-forge-ci-setup also when using `c_stdlib_version` (#1884 via #1889)
* Update ``github_actions.free_disk_space`` to match Azure's ( #1882 )

**Authors:**

* Jaime Rodríguez-Guerra
* H. Vetinari
* John Kirkham
* Yannik Tausch



v3.33.0
====================

**Added:**

* Support Apple silicon runners on GHA hosted (#1872, #1874).

**Changed:**

* Stop using conda_build.conda_interface. (#1868)
* Allow any ``str`` in ``conda-forge.yml``'s ``skip_render`` key. (#1875 via #1878)

**Fixed:**

* Update ``BotConfig`` schema description with examples of all possible values. (#1861 via #1862)
* Added missing ``azure: build_id`` into the json schema. (#1871)
* Add more skip render choices (#1873).
* Allow ``str`` (in addition to list of ``str``) in ``conda-forge.yml``'s ``noarch_platforms`` and ``remote_ci_setup``. (#1869 via #1877)

**Authors:**

* Isuru Fernando
* Jaime Rodríguez-Guerra
* Marcel Bargull
* pre-commit-ci[bot]



v3.32.0
====================

**Added:**

* New JSON schema for ``conda-forge.yaml``. A Pydantic model is used to dynamically generate both a YAML document with the default values and the JSON schema itself. (#1756)
* Included ``jsonschema`` and ``pydantic`` as dependencies into the ``environment.yml``. (#1756)

**Changed:**

* Included extra ``jsonschema`` validation for conda-forge.yaml, under ``configure_feedstock``. (#1756)
* Moved legacy checks of old_file and providers into a new auxiliary ``_legacy_compatibility_checks`` function. (#1756)
* Use Azure owner in URL for missing token error message. (#1854)
* Invoke conda-{build,mambabuild} directly, not as conda subcommand. (#1859)

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Jaime Rodríguez-Guerra
* Marcel Bargull
* vinicius douglas cerutti
* pre-commit-ci[bot]
* John Blischak



v3.31.1
====================

**Changed:**

* Do not consider broken releases when checking if local version is up to date. (#1848 via #1849)
* Added rerendering support for additional mpi variants ``msmpi``, ``mpi_serial``, and ``impi``.

**Fixed:**

* Fixed regression where some variant keys were mismatched during rerendering.

**Authors:**

* Matthew R. Becker
* Jaime Rodríguez-Guerra



v3.31.0
====================

**Added:**

* Smithy now understand the new stdlib jinja function.
* Complete conda-build load data functions stubs PR #1829
* `noarch` packages can now include keys from their `conda_build_config.yaml` as selectors in their recipe.
This allows for building multiple variants of a `noarch` packages, e.g., to use different dependencies depending on the Python version as runtime.

**Changed:**

* Default build tool changed from conda-mambabuild to conda-build again. (#1844)
* Cleanup ``run_win_build.bat`` ( #1836 )

**Fixed:**

* Resolve warnings in Github Actions workflows by updating to ``actions/checkout@v4``. (#1839)
* Fix randomly mismatched zipped variant keys. (#1459 and #1782 via #1815)

**Authors:**

* Jaime Rodríguez-Guerra
* Marcel Bargull
* John Kirkham
* H. Vetinari
* Bela Stoyan
* pre-commit-ci[bot]
* Matthias Diener
* Antonio S. Cofiño



v3.30.4
====================

**Changed:**

* Fixed a typo in gitignore (#1822).

**Fixed:**

* Code refactoring for cirun. (#1812)

**Authors:**

* Isuru Fernando



v3.30.3
====================

**Changed:**

* Fixed gitignore so that maturin projects work.

**Fixed:**

* Fixed line endings of .ci_support/README on windows (#1824).
* Fix local builds of feedstocks submodules ( #1826 ).

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Marcel Bargull
* John Kirkham
* pre-commit-ci[bot]
* David Hirschfeld



v3.30.2
====================

**Added:**

*  <news item>

**Changed:**

* Updated `.gitignore` to exclude everything except recipe/ and conda-forge.yml (#1413)

**Fixed:**

* Fix linting with conda-build=3.28.2. (#1816)

**Authors:**

* Isuru Fernando
* Marcel Bargull
* pre-commit-ci[bot]
* David Hirschfeld



v3.30.1
====================

**Added:**

* Support setting teams, roles and users_from_json in cirun (#1809).
* Don't skip testing in win if there is an emulator.

**Authors:**

* Isuru Fernando



v3.30.0
====================

**Changed:**

* Set ``conda_build_tool: mambabuild`` as default again until
  https://github.com/conda/conda-libmamba-solver/issues/393 is fixed (#1807).
* Changes the xkcd comic in the README to 1319 ( #1802 ) ( #1803 )

**Authors:**

* Marcel Bargull
* John Kirkham



v3.29.0
====================

**Added:**

* Added an --without-all option to ci-register/register-feedstock-token to disable all CI
  and --with-<ci> would selectively enable the CI service (#1793, #1796).
* Added a lint to check that staged-recipes maintainers have
  commented on the PR that they are willing to maintain the recipe. (#1792)

**Changed:**

* Require pygithub>=2 as github actions secrets need that version. (#1797)
* When upload_on_branch is set, GHA is triggered only for that branch (#1687).

**Fixed:**

* The team name for cirun was fixed. Previously the team name passed had
  -feedstock in it and also did not support teams as maintainers.
  For teams like conda-forge/r, if they are added to a feedstock after
  Cirun is configured, the feedstock needs to be reconfigured (#1794).
* Fixed getting cirun installation id for non conda-forge orgs (#1795).
* Fix name of anaconda.org in README template, to prevent confusion with anaconda.cloud (#1798).
* Skip running some tests locally when GH_TOKEN is not set (#1797).

**Authors:**

* Isuru Fernando
* Jaime Rodríguez-Guerra
* Bastian Zimmermann
* pre-commit-ci[bot]
* Jannis Leidel



v3.28.0
====================

**Added:**

* For self-hosted github actions runs, a user can add custom labels
  by adding `github_actions_labels` yaml key in `recipe/conda_build_config.yaml`.
  The value `hosted` can be used for Microsoft hosted free runners
  and the value `self-hosted` can be used for the default self-hosted labels.

* `github_actions: timeout_minutes` option added to change the timeout in minutes.
  The default value is `360`.

* `github_actions: triggers` is a list of triggers which defaults to
  `push, pull_request` when not self-hosted and `push` when self-hosted.

* Added a `--cirun` argument to `conda-smithy ci-register` command to register
  `cirun` as a CI service. This makes `cirun` conda package a dependency of
  conda-smithy.

* Added support for `cirun` by generating a unique label when the self-hosted
  label starts with `cirun`.

* When a label is added that has the string with `gpu` or `GPU` for a self-hosted
  runner, the docker build will pass the GPUs to the docker instance.
* Add ``flow_run_id`` (CI provider specific), ``remote_url`` and ``sha`` as extra-meta data to packages.
  Enables tracing back packages to a specific commit in a feedstock and to a specific CI run.
  When packages are built using ``build-locally.py`` only ``sha`` will have a non-empty value.
  Requires ``conda-build >=3.21.8``. (#1577)

**Changed:**

* `github_actions: cancel_in_progress` option added to cancel in progress runs.
  The default value was changed to `true`.
* Use the channels defined in `conda_build_config.yaml` (instead of those in `conda-forge.yml`) to render `README.md`. (#897 via #1752, #1785)
*  Allow finer control over Azure disk cleaning ( #1783 )
* The default build tool changed from conda-mambabuild to conda-build with
  libmamba solver.

**Authors:**

* Isuru Fernando
* Jaime Rodríguez-Guerra
* Amit Kumar
* John Kirkham
* Daniel Bast
* Daniel Ching
* pre-commit-ci[bot]



v3.27.1
====================

**Fixed:**

* Crash when XDG_CACHE_DIR is defined

**Authors:**

* Min RK



v3.27.0
====================

**Added:**

* Cache the contents of ``conda-forge-pinning`` and only check every 15min for an updated version.
  The re-check interval can be configured via the ``CONDA_FORGE_PINNING_LIFETIME`` environment variable.

**Changed:**

* Do not strip version constraints for ``mamba update``. (#1773 via #1774)
* If one supplies ``--no-check-uptodate`` on the commandline, we will no longer check and print a warning if conda-smithy is outdated.

**Removed:**

* Removed the ``updatecb3`` command. It is advised to do this update manually if you still encounter a recipe using the old compiler ``toolchain``.

**Authors:**

* Jaime Rodríguez-Guerra
* Uwe L. Korn



v3.26.3
====================

**Changed:**

* The package hints of the linter are now taken from a location that doesn't require new smithy releases to change.
* Fix ``MatchSpec`` parsing when ``remote_ci_setup`` specs are quoted. (#1773 via #1775)

**Authors:**

* Jaime Rodríguez-Guerra
* H. Vetinari



v3.26.2
====================

**Fixed:**

* Fixed additional_zip_keys, so that subsequent migrations don't break.

**Authors:**

* Bela Stoyan



v3.26.1
====================

**Fixed:**

* Set ``FEEDSTOCK_NAME`` correctly on Windows in Azure Pipelines. (#1770)
* Always use ``conda`` to ``uninstall --force``. (#1771)

**Authors:**

* Jaime Rodríguez-Guerra



v3.26.0
====================

**Added:**

* ``conda_build_tool`` setting with four different options: ``conda-build``, ``mambabuild`` (default),
  ``conda-build+conda-libmamba-solver`` and ``conda-build+classic``. - #1732
* Add ``conda_install_tool`` and ``conda_solver`` configuration options to allow choosing between
  ``mamba`` and ``conda`` (with ``classic`` or ``libmamba`` solvers) as the dependency
  handling tools. (#1762, #1768)
* Add ``additional_zip_keys`` configuration option for migrations (#1764)

**Changed:**

* Unified Windows build scripts to avoid duplication of template logic in Github Actions and Azure Pipelines. (#1761)
* Use strict channel priority on Linux and macOS. (#1768)
* Use ``python-build`` to create ``sdist`` #1760

**Deprecated:**

* ``build_with_mambabuild`` boolean option is deprecated. Use ``conda_build_tool: mambabuild`` instead. - #1732

**Fixed:**

* Ensure undefined Jinja variables are rendered as the variable name, restoring Python 2-like behaviour. (#1726 via #1727)
* Use name-only specs in ``conda update`` and ``conda uninstall`` subcommands. (#1768)
* Catch negative exit codes on Windows. (#1763)
* Fixed bug in the display of grouping commands in the Travis CI logging utilities. (#1730)

**Authors:**

* Jaime Rodríguez-Guerra
* Uwe L. Korn
* John Kirkham
* Peter Williams
* Bela Stoyan
* Klaus Zimmermann



v3.25.1
====================

**Fixed:**

* Ensure ``swapfile_size`` is not added to the Azure job settings #1759

**Authors:**

* John Kirkham



v3.25.0
====================

**Added:**

* Added ability for select feedstocks (pinnings, smithy, repodata patches) to use GHA in conda-forge.
  Items can be added by setting the ``CONDA_SMITHY_SERVICE_FEEDSTOCKS`` environment variable to a
  comma-separated list of additional feedstocks.

**Changed:**

* Add option to cleanup GHA images - #1754
* Created option to create a swap file on the default linux image on Azure Pipelines

**Fixed:**

* Allow operators in noarch platform selectors

**Authors:**

* Matthew R. Becker
* Jaime Rodríguez-Guerra
* Mike Henry
* John Kirkham



v3.24.1
====================

**Added:**

* Add GHA option to limit number of parallel jobs - #1744

**Changed:**

* Free up more space on the default linux image on Azure Pipelines

**Fixed:**

* Avoid needing to activate environment to use conda-smithy

**Authors:**

* Matthew R. Becker
* Mark Harfouche
* Chris Burr
* Billy K. Poon
* John Kirkham



v3.24.0
====================

**Added:**

* Added linting for obsoleted outputs, e.g. those who have been renamed conda-forge-wide.
*  Support not running tests when cross compiling in win - #1742

**Fixed:**

* Fixed bug in codepath to allow debugging of cross compiled OSX configuratons using ``build-locally.py``.
* Fixed README headers for recipes with multiple outputs

**Authors:**

* Isuru Fernando
* Mark Harfouche
* H. Vetinari
* John Blischak



v3.23.1
====================

**Fixed:**

* Fix "prepare conda build artifacts" step failing on Azure + Windows with the error "The syntax of the command is incorrect" (#1723).

**Authors:**

* Ryan Volz



v3.23.0
====================

**Added:**

* Added capability to generate feedstock tokens per CI provider.
* Added token expiration timestamps.

**Changed:**

* Move pre-commit to its own CI test file.
* Added ``--no-build-isolation`` to pip commands for install.
* Remove ``py-lief<0.12`` from ``remote_ci_setup`` after LIEF 0.12.3 release
* Windows CI on azure uses python 3.10 in the base environment.
* Replaced deprecated use of ::set-output during conda artifact storage on GitHub Actions with the recommended redirect to $GITHUB_OUTPUT. See https://github.blog/changelog/2022-10-11-github-actions-deprecating-save-state-and-set-output-commands/.
* Default branch for github is now ``main`` instead of ``master``.
* Changed python packaging to use setuptools-scm instead of versioneer.
* Moved build system to only use ``pyproject.toml``.
* skip_render can match Path().parents of files being rendered
  i.e. '.github' in list prevents rendering .github in toplevel
  and any files below .github/
* Changed default image for windows to `windows-2022`.

**Fixed:**

* `README.md` of feedstocks with multiple outputs is now correctly rendered with all outputs's (about) information shown, unless they are a plain copy of the top-level about.
* skip_render can prevent github webservices from rendering
* Always check team membership even when making teams.

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Leo Fang
* Marcel Bargull
* Ryan Volz
* Mark Harfouche
* Tim Snyder
* H. Vetinari



v3.22.1
====================

**Changed:**

* Use a custom %TEMP% directory to avoid upload permission errors on Windows.

**Authors:**

* Marcel Bargull



v3.22.0
====================

**Changed:**

* Changed the pinning package extraction code to account for ``.conda`` files
  and to use ``conda-package-handling``.

**Authors:**

* Matthew R. Becker



v3.21.3
====================

**Added:**

* Added support for aarch64 native runners on circle CI

**Changed:**

* Upgrade to actions/checkout@v3
* Upgrade to actions/upload-artifact@v3
* Add ``py-lief<0.12`` to ``remote_ci_setup`` for now
  due to current ``osx-*`` segfault issues, ref:
  https://github.com/conda-forge/conda-forge.github.io/issues/1823
* recipes with ``noarch_platforms`` will no longer give a lint when selectors are used.

**Fixed:**

* Fix Azure urls in details

**Authors:**

* Isuru Fernando
* Johnny Willemsen
* Marcel Bargull
* Marius van Niekerk
* Brandon Andersen



v3.21.2
====================

**Changed:**

* ``conda-smithy`` will not check which ``conda`` version is installed anymore.
  ``conda`` follows CalVer now, which does not provide information about API guarantees,
  thus rendering this check moot.

**Fixed:**

* Fix ``pyproject.toml`` derived issues with CI tests

**Authors:**

* Jaime Rodríguez-Guerra



v3.21.1
====================

**Changed:**

* macOS jobs provided by Azure Pipelines will now use the ``macOS-11`` VM image (#1645).

**Fixed:**

* Fix spurious lint when using pin_subpackage or pin_compatible with a build string

**Authors:**

* Jaime Rodríguez-Guerra
* Min RK



v3.21.0
====================

**Added:**

* All conda packages will have the license file included alongside
  the rendered recipe.
* conda-smithy now reports lint if pin_compatible or pin_subpackage are used
  with the wrong package type.

**Changed:**

* build_locally now creates conda's shared package cache outside the container,
  so repeated builds of the same recipe do not need to redownload packages.
* ``mamba`` is now used in the CI tests for conda-smithy

**Fixed:**

* Fix the support of `idle_timeout_minutes` for Travis CI

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Leo Fang
* Tim Snyder
* Daniel Ching
* Nicholas Bollweg



v3.20.0
====================

**Changed:**

* circleci linux image to latest ubuntu for
  https://circleci.com/blog/ubuntu-14-16-image-deprecation/
* Switched to using Miniforge to setup CI environment in Azure

**Removed:**

* Removed vs2008 support in azure

**Fixed:**

* Fixed an error with downgrading conda

**Authors:**

* Isuru Fernando
* Tim Snyder
* Nicholas Bollweg



v3.19.0
====================

**Added:**

* noarch packages that cannot be built on ``linux_64`` can be configured to build
  on one or more ``noarch_platforms`` in ``conda-forge.yml``

**Changed:**

* Default provider for aarch64 and pcp64le is now Travis-CI

**Fixed:**

* Travis CI badge in readme uses correct url and linux image

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Nicholas Bollweg
* Sylvain Corlay



v3.18.0
====================

**Deprecated:**

* We have deprecated the usage of Travis CI for any platforms but linux_aarch64, linux_ppc64le, or
  linux_s390x. Conda-smithy will raise a RuntimeError if one attempts to render a recipe for a different platform.

**Fixed:**

* Fixed rotation token for gha
* Fixed a bug where mpich and openmpi pins were not appearing properly due non-recursive parsing in smithy.

**Authors:**

* Isuru Fernando
* Matthew R. Becker



v3.17.2
====================

**Fixed:**

* Fixed bug where remote ci setup removed boa too.

**Authors:**

* Isuru Fernando
* Matthew R. Becker



v3.17.1
====================

**Fixed:**

* Fixed issue with CLI argument for feedstock token commands.

**Authors:**

* Mervin Fansler



v3.17.0
====================

**Added:**

* When rotating tokens, update the token in GHA too
* The variable 'BUILD_WITH_CONDA_DEBUG' (and thus build-locally.py's '--debug' flag) is now honored on macOS.
* Users may now specify a list of packages as part of the ``remote_ci_setup``
  entry in ``conda-forge.yml`` to install more packages as part of the setup
  phase.

**Changed:**

* Drop ``defaults`` from ``channel_sources``
* The SPDX identifier list has been updated.
* Updated ``.ci_support/README`` for improved clarity.

**Fixed:**

Fixed a bug in run_docker_build.sh when finding the value of FEEDSTOCK_ROOT.
In some cases the cd command had output to stdout which was included in
FEEDSTOCK_ROOT. Now the value is computed as for THISDIR in the same script,
with the output of cd redirected to /dev/null.
*Clarify in build-locally.py that setting OSX_SDK_DIR implies agreement to the SDK license.
* Added .ci_support/README to generated file list

**Authors:**

* Isuru Fernando
* Uwe L. Korn
* Mark Harfouche
* John Kirkham
* Bastian Zimmermann
* Matthias Diener
* Philippe Blain
* Benjamin Tovar



v3.16.2
====================

**Changed:**

* Happy New Year! The license now includes 2022.
* Default provider for ppc64le was changed to azure with emulation using qemu.

**Authors:**

* Isuru Fernando
* Bastian Zimmermann



v3.16.1
====================

**Fixed:**

* Fixed error in linter for ``matplotlib-base`` for multioutput recipes where the requirements are a list.

**Authors:**

* Matthew R. Becker



v3.16.0
====================

**Added:**

* Added rerendering token input to webservices github action and automerge github action.

**Authors:**

* Matthew R. Becker



v3.15.1
====================

**Added:**

* Added a hint for recipes in conda-forge to depend on matplotlib-base as opposed to
  matplotlib.

**Changed:**

* use python 3.9 on github actions and use mambaforge
* When building with boa, use mamba to install conda-build, etc.  This assumes that
  we are using a Mambaforge based docker image / runtime environment.
* For azure pipelines, the default windows image is changed to windows-2019

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Marius van Niekerk



v3.15.0
====================

**Added:**

* Conda smithy will now detect if a recipe uses ``compiler('cuda')``
and set the ``CF_CUDA_ENABLED`` environment variable to ``True`` if
so. This can for example be useful to distinguish different options
for builds with or without GPUs in ``conda_build_config.yaml``.
* Introduce utility function to facilitate the use case of running conda smithy
  commands from any sub-directory in the git repo checkout of a feedstock.

**Fixed:**

* Fixed typo in GitHub Actions template, where ``DOCKERIMAGE`` was wrongly specified in the matrix configuration. The CI step and its corresponding script expect ``DOCKER_IMAGE``.

**Authors:**

* Isuru Fernando
* Jaime Rodríguez-Guerra
* H. Vetinari
* Nehal J Wani



v3.14.3
====================

**Changed:**

* linux-aarch64 builds default is changed from native (drone) to emulated (azure).

**Authors:**

* Isuru Fernando
* Mike Taves



v3.14.2
====================

**Authors:**

* Isuru Fernando



v3.14.2
====================

**Added:**

* Download SDK to local folder when build-locally.py instead of to the system dir
* Added support for woodpecker CI support

**Authors:**

* Isuru Fernando



v3.14.1
====================

**Fixed:**

* Call ``docker pull`` then ``docker run`` (sometimes ``--pull`` is unavailable)

**Authors:**

* Matthew R. Becker
* John Kirkham



v3.14.0
====================

**Added:**

* ``test`` option in ``conda-forge.yml`` can now be used to configure testing.
  By default testing is done for all platforms. ``native_and_emulated`` value
  will do testing only if native or if there is an emulator. ``native`` value
  will do testing only if native.

**Deprecated:**

* ``test_on_native_only`` is deprecated. This is mapped to
  ``test: native_and_emulated``.

**Fixed:**

* Always pull a new version of the image used in a build
* Add workaround for Travis CI network issues (courtesy of @pkgw)

**Authors:**

* Isuru Fernando
* Marcel Bargull
* Matthew W. Thompson



v3.13.0
====================

**Added:**

* Added the ability to store conda build artifacts using the Github Actions provider. To enable, set `github_actions: {store_build_artifacts: true}` in conda-forge.yml.
* It is possible to set the lifetime of the Github Actions artifacts by setting the the `github_actions: {artifact_retention_days: 14}` setting in conda-forge.yml to the desired value. The default is 14 days.
* Support for ppc64le on drone CI has been added
* Added support for registering at a custom drone server by adding --drone-endpoint cli argument
* Added explicit check to not upload packages on PR builds.
* Added key ``github:tooling_branch_name`` to ``conda-forge.yml`` to enable
  setting the default branch for tooling repos.
* The linter will now warn if allowed ``pyXY`` selectors are used (e.g. ``py27``, ``py34``, ``py35``, ``py36``). For other versions (e.g. Python 3.8 would be ``py38``), these selectors are *silently ignored*  by ``conda-build``, so the linter will throw an error to prevent situations that might be tricky to debug. We recommend using ``py`` and integer comparison instead. Note that ``py2k`` and ``py3k`` are still allowed.
* Added support for self-hosted github actions runners

  In conda-forge.yml, add ``github_actions: self_hosted: true`` to
  enable self-hosted github actions runner. Note that self-hosted
  runners are currently configured to run only on push events
  and pull requests will not be built.

* Allow multiple providers per platform

  In conda-forge.yml, add ``provider: <platform>: ['ci_1', 'ci_2']``
  to configure multiple providers per platform.

**Changed:**

* Uploads are now allowed when building with ``mambabuild``!
* Azure build artifacts are now zipped before being uploaded, with some cache directories and the conda build/host/test environments removed, to make user download smaller and faster.
* A separate Azure build artifact, including only the conda build/host/test environments, is additionally created for failed builds.
* Azure artifact names are now only shortened (uniquely) when necessary to keep the name below 80 characters.
* Updated CircleCI xcode version to 13.0.0 to prevent failures.
* The conda-smithy git repo now uses ``main`` as the default branch.
* conda mambabuild is now the default build mode.  To opt out of this change set ``build_with_mambabuild`` to false in your ``conda-forge.yml``.
* Bump Windows ``base`` environment Python version to 3.9
* Support using ``build-locally.py`` natively on ``osx-arm64``.

**Fixed:**

* Azure artifact names are now unique when a job needs to be restarted (#1430).
* Azure artifact uploads for failed builds that failed because of broken symbolic links have now been fixed.
* Test suite now runs correctly on pyyaml 6
* Remove the miniforge installation before building with ``./build-locally.py`` on MacOS so that
  ``./build-locally.py`` can be run more than once without an error regarding an exisiting miniforge installation.

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Jaime Rodríguez-Guerra
* Uwe L. Korn
* Ryan Volz
* John Kirkham
* Wolf Vollprecht
* Marius van Niekerk
* Matthias Diener



v3.12
====================

**Authors:**

* Marius van Niekerk



v3.12
====================

**Changed:**

* conda smithy init will now copy over the conda-forge.yml from the source recipe directory (if present)

**Authors:**

* Marius van Niekerk



v3.11.0
====================

**Added:**

* The maximum number of parallel jobs a feedstock can run at once will be limited
  to ``50``. This will ensure that all projects have a fair access to CI resources
  without job-hungry feedstocks hogging the build queue.

**Fixed:**

* Add --suppress-variables flag to conda-build command in Windows template

**Authors:**

* Jaime Rodríguez-Guerra
* Billy K. Poon



v3.10.3
====================

**Fixed:**

* Linting of recipes with multiple URLs was broken in last release and is fixed now

**Authors:**

* Isuru Fernando



v3.10.2
====================

**Added:**

* Add a "--feedstock_config" option to the regenerate/rerender, update-anaconda-token, azure-buildid subcommands for providing an alternative path to the feedstock configuration file (normally "conda-forge.yml"). This allows different names or to put the configuration outside the feedstock root.
* Linter will now check for duplicates of conda packages using pypi name
* Validate the value of ``noarch``. (Should be ``python`` or ``generic``.)

**Changed:**

* Use ``ubuntu-latest`` instead of ``ubuntu-16`` in the Azure pipeline template.

**Fixed:**

* `short_config_name` is used at azure pipelines artifact publishing step.
* Duplicate feedstocks with only '-' vs '_' difference is now correctly checked.
* correctly detect use of `test/script` in outputs

**Authors:**

* Isuru Fernando
* Uwe L. Korn
* Ryan Volz
* Duncan Macleod
* fhoehle
* Ben Mares



v3.10.1
====================

**Added:**

* Allow osx builds in build-locally.py

**Changed:**

* Focal is now used for Linux builds on Travis CI

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Chris Burr





v3.10.0
====================

**Added:**

* Added `clone_depth` parameter for use in conda-forge.yml that sets the feedstock git clone depth for all providers (except CircleCI). By default (`clone_depth: none`), current behavior is maintained by using the provider's default checkout/clone settings. A full clone with no depth limit can be specified by setting `clone_depth: 0`.
* Log groups support for GitHub Actions
* Added support for Github Actions as a CI provider. Provider name to use in conda-forge.yml
  is `github_actions`. Note that Github Actions cannot be enabled as a CI provider for conda-forge
  github organization to prevent a denial of service for other infrastructure.
* Add instructions to feedstock README template for configuring strict channel priority.

**Changed:**

* The `ci-skeleton` command now creates a default conda-forge.yml that sets `clone_depth: 0` for full depth clones on all providers. This default supports expected behavior when using `GIT_DESCRIBE_*` to set version and build numbers in the recipe by ensuring that tags are present. This effectively changes the default clone behavior for the Github Action and Travis providers, as all other providers do a full clone by default.

**Fixed:**

* Prevent duplicated log group tags when ``set -x`` is enabled.
* Fix run_osx_build not failing early on setup error.
* Fix too long filenames for build done canary files.

**Authors:**

* Isuru Fernando
* Jaime Rodríguez-Guerra
* Ryan Volz
* Marcel Bargull
* Philippe Blain
* Matthew R. Becker
* Marcel Bargull



v3.9.0
====================

**Added:**

* Enabled multiple entries for ``key_add`` operations.
* Define Bash functions ``startgroup()`` and ``endgroup()`` that provide a
  provider-agnostic way to group or fold log lines for quicker visual inspection.
  In principle, this only affects Linux and MacOS, since Windows pipelines
  use CI native steps. So far, only Azure and Travis support this. In the other
  providers a fallback ``echo "<group name>"`` statement is supplied.
* Support `os_version` in `conda-forge.yml`
* Add use_local option to use the migrator from the feedstock

**Changed:**

* To cross compile for  ``win-32`` from ``win-64``, using ``target_platform``
  is no longer supported. Use ``build_platform: win_32: win64`` in ``conda-forge.yml``.
* `run_osx_build.sh` had hardcoded handlers for Travis log folding. These have
  been replaced with the now equivalent Bash functions.
* A lower bound on python version for noarch python is now required

**Fixed:**

* Fix "File name too long" error for many zip keys
  Replace config filenames by their short versions if filesystem limits
  are approached.
* Fix running ``./build-locally.py --debug`` with cross-compilation
* Fixed dead conda-docs link to the ``build/number`` explanation in the README template.
* Fixed rendering error where the recipe's ``conda_build_config.yaml`` is
  applied again, removing some variants.
* Fixed list formatting in the README.
* migration_ts and migrator_ts were both used in conda-smithy and migration_ts was removed in favour of migrator_ts

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Jaime Rodríguez-Guerra
* Chris Burr
* Leo Fang
* Marcel Bargull
* Wolf Vollprecht
* Hugo Slepicka
* Bastian Zimmermann



v3.8.6
====================

**Changed:**

* Run docker builds using ``delegated`` volume mounts.

**Fixed:**

* All keys zipped with ``docker_image`` are now handled properly.
* Changed CI configuration to not run tests on ``push`` events to branches that
  are not ``master``.
* CI runs on PRs from forks now.
* ``#`` is not a valid comment symbol on Windows and using it as part of a pipeline Batch step will cause a (harmless) error in the logs. It has been replaced by ``::`` instead.

**Security:**

* Use latest ``conda-incubator/setup-miniconda`` version to circumvent the GH Actions deprecations on Nov 16th

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Matthew R. Becker
* Uwe L. Korn
* John Kirkham
* Jaime Rodríguez-Guerra



v3.8.5
====================

**Changed:**

* Moved CI to GitHub actions and removed travis-ci
* Use the shorter build ID instead of job ID to name Azure artifacts when they are stored. This helps prevent the artifact name from being too long, which would result in being unable to download it.
* Replaced travis-ci status badge w/ GitHub actions one.

**Fixed:**

* Faulty ``migrator_ts`` type check prevented manual migrations from happening (those that are not yet merged to ``conda-forge-pinning``).
* Previous release accidentally included a commit that made noarch: python
  recipes without a lower bound error. This was changed to a hint

**Authors:**

* Isuru Fernando
* Matthew R. Becker
* Ryan Volz
* Marius van Niekerk
* Jaime Rodríguez-Guerra



v3.8.4
====================

**Fixed:**

* conda-build 3.20.5 compatibility for ``target_platform`` being always defined.

**Authors:**

* Isuru Fernando



v3.8.3
====================

**Added:**

* conda-build 3.20.5 compatiblity
* New ``choco`` top-level key in ``conda-forge.yml`` enables windows builds
  to use chocolatey to install needed system packages. Currently, only Azure
  pipelines is supported.

**Authors:**

* Isuru Fernando
* Anthony Scopatz



v3.8.2
====================

**Changed:**

* Reverted bugfix for each compiler getting a CI job.

**Authors:**

* Matthew R. Becker



v3.8.1
====================

**Changed:**

* Removed the default concurrency limits for azure

**Fixed:**

* Fixed rendering to make sure CI jobs are generated for each compiler version.

**Authors:**

* Matthew R Becker
* Filipe Fernandes
* Matthew R. Becker
* Marius van Niekerk



v3.8.0
====================

**Added:**

* Generate Documentation and Development links into the README.md based on doc_url and dev_url
* Add hyperlink to feedstock license file
* Generate license_url as hyperlink in the README.md when it has been defined in the meta.yaml
* Add ``--without-anaconda-token`` option to register-ci command, keep default behaviour of requiring the token
* ``remote_ci_setup`` field in conda-forge.yml, which defaults to ``conda-forge-ci-setup=3`` allowing the user to override

**Changed:**

* Variant algebra now supports two new operations for adding/remove a key

These new options allow for handling complex migrations cases needed for the python migrations.
* Add support to ``build-locall.py`` to call ``conda debug``.
* Added note about behaviour to README.md
* CI templates now expand ``remote_ci_setup`` string from config for the ci setup package

**Removed:**

* Remove unneeded set_defaults() for --without-$CI args, ``action="store_false"`` already defaults to True if not given

**Fixed:**

* Removed the warning for azure token when rerendering

**Authors:**

* Isuru Fernando
* Johnny Willemsen
* Uwe L. Korn
* Tom Pollard
* Marius van Niekerk



v3.7.10
====================

**Removed:**

* Remove unused ``forge_config["upload_script"]`` logic

**Fixed:**

* Error with linting check for deletion of ``recipes/example/meta.yaml`` in staged-recipes

**Authors:**

* Joshua L. Adelman
* Tom Pollard



v3.7.9
====================

**Added:**

* ``test_on_native_only`` is now supported on osx too.

**Deprecated:**

* Unparsed `"upload_packages": False` from default conda-forge.yml, as not parsed & no longer reflective of defaults

**Fixed:**

* re-enabled `upload_packages` per provider to conda-forge.yml, which when set to False overrides default upload logic

**Authors:**

* Isuru Fernando
* Tom Pollard
* Joshua L. Adelman



v3.7.8
====================

**Added:**

* ``MACOSX_SDK_VERSION`` is added as an always used key

**Authors:**

* Isuru Fernando



v3.7.7
====================

**Added:**

* Publish conda build artifacts on Azure as pipeline artifacts when azure.store_build_artifacts flag is True in conda-forge.yml. The default is False.
* Add an option ``test_on_native_only`` to not run tests when cross compiling

**Changed:**

* Handle NameError when anaconda_token isn't defined in ci_register.py, inline with rotate_anaconda_token()
* MacOS image in CI is bumped to macOS 10.15

**Fixed:**

* Re add travis_wait support via idle_timeout_minutes

**Authors:**

* Isuru Fernando
* Ryan Volz
* Tom Pollard



v3.7.6
====================

**Added:**

* Added partial support for cross compiling (Unixes can compile for other unixes only)

**Changed:**

* linux-64 configs were changed from prefix ``linux`` to ``linux-64``
* ``target_platform`` is now always defined for non-noarch  recipes
* Raise RuntimeError on empty travis repo_info requests, to guard against later KeyErrors
* Provide the name of the feedstock for which the update-anaconda-token command
  was performed.
* GitHub Teams are now added to feedstocks by their ``slug`` (i.e., the name
  used to ``@``-mention them on ``github.com``) as opposed to their names.

**Deprecated:**

* Setting ``provider: linux`` is deprecated in favor of ``provider: linux_64``

**Fixed:**

* Use `simplejson` to catch `JSONDecodeError` when available. Fix #1368.

**Security:**

* Members and teams are now properly removed from feedstocks and feedstock
  maintenance teams.

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Matthew R. Becker
* Hadrien Mary
* Maksim Rakitin
* Tom Pollard



v3.7.4
====================

**Added:**

* Use the anaconda API to retrieve the latest version number of ``conda-smithy`` and ``conda-forge-pinning``.
* Pass ``CPU_COUNT`` from the host environment to the docker build.
  (Convenient when building locally.)
* Add a flag to `register-github` to create a private repository.
* Add a `private_upload` key in conda config file. If set to True Anaconda upload will use the `--private` flag.
* Removes ``/opt/ghc`` on Azure Linux images to free up space
* Additional secrets can be passed to the build by setting `secrets: ["BINSTAR_TOKEN", "ANOTHER_SECRET"]`
  in `conda-forge.yml`. These secrets are read from the CI configuration and
  then exposed as environment variables. To make them visible to build scripts,
  they need to be whitelisted in `build.script_env` of `meta.yaml`.
  This can, e.g., be used to collect coverage statistics during a build or test
  and upload them to sites such as coveralls.

**Changed:**

* Return type of ``feedstocks.clone_all()`` from ``None`` to list of repositories
* Link to list of SPDX licenses in lint message.

**Fixed:**

* Use ``AzureConfig`` in ``render_README`` instead of calling a raw requests. It allows rendering on a private Azure CI organization.
* CI skeleton properly sets the build number
* use SPDX identifier for feedstock license
* Allow an empty conda-forge.yml.
* The repo name for output validation is now extracted in the CI services to avoid
  issues with bad rerenders for clones to non-standard locations.

**Security:**

* Added --suppress-variables so that CI secrets cannot be leaked by conda-build into CI logs.

**Authors:**

* Matthew R Becker
* Christopher J. Wright
* Matthew R. Becker
* Hadrien Mary
* Julian Rüth
* Uwe L. Korn
* John Kirkham
* Duncan Macleod
* Axel Huebl
* Thomas Hopkins
* Stuart Berg



v3.7.3
====================

**Fixed:**

* Get feedstock name from meta when registering with CI services.
* CODEOWNERS file no longer treats GitHub team names as case-sensitive.

**Authors:**

* Matthew R Becker
* Uwe L. Korn



v3.7.2
====================

**Changed:**

* Changed the automerge configuration to use conda-forge/automerge-action.

**Authors:**

* Matthew R Becker



v3.7.1
====================

**Added:**

* Added ci skip statements during token registration to reduce loads.
* Added tar as a dependency
* Option to specify the generated feedstock name via ``extra.feedstock-name``.
* Support self-hosted Azure agents

**Changed:**

* Changed the docker mount to the recipe directory to have read-write permissions instead
  of read-only.
* conda-forge-pinning package is now downloaded on the fly

**Fixed:**

* Fix folding scripts file in GH PRs
* Error when linting recipes with ``license_file: `` (i.e. no file specified)
* PSF-2.0 is not a deprecated license
* Fixed whitespace additions

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Matthew R. Becker
* Chris Burr
* Leo Fang
* Uwe L. Korn



v3.7.0
====================

**Added:**

Added a linter check for already existing feedstocks that are not exact match, but may have underscore instead of dash, and vice versa.
* Added code to rotate anaconda tokens.
* Added new `pip-install`-based hooks for using a local copy of the
  `conda-forge-ci-setup` package.

**Changed:**

* Refactored OSX CI scripts to be based off of a single global script on all CI platforms.
* Renamed the feedstock token output files to not munge "-feedstock" from
  the names.

* Bumped the default version of the `conda-forge-ci-setup` package to 3 to
  support the new output validation service.

**Fixed:**

* Fixed bug in feedstock token registration that deleted other secrets from azure.
* Fixed bugs in tests for feedstock tokens.

**Security:**

* Added code to call the feedstock output validation service. You must have
  `conda_forge_output_validation` set to true in the `conda-forge.yml` to use
  this feature.

**Authors:**

* Matthew R Becker
* Matthew R. Becker
* Natasha Pavlovikj



v3.6.17
====================

**Added:**

* Added a linter check for jinja2 variables to be of the form ``{{<one space><variable name><one space>}}``.

**Changed:**

* Change azure.force default to False in conda-forge.yml (#1252)
* Use a faster script for removing homebrew on osx.

**Removed:**

* Removed No azure token warning when rerendering
* Deleting strawberry perl was removed as conda-forge-ci-setup now filters the PATH
* Removed fast finish script for travis as we now set the setting on travis

**Fixed:**

* Re-rendering now cleans old contents in ``.azure-pipelines``
* Fixed the drone CI badge
* Made yaml loading in conda_smithy thread safe

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Matthew R. Becker
* John Kirkham
* Tim Snyder
* Peter Williams



**Changed:**

* Allow people to pass extra arguments to ``docker run`` by setting
  ``$CONDA_FORGE_DOCKER_RUN_ARGS``.

**Authors:**

* Peter K. G. Williams



v3.6.16
====================

**Changed:**

* Windows conda environment is activated before conda calls
* Moved the appveyor image to Visual Studio 2017.

**Fixed:**

* Linter now properly allows ``LicenseRef`` and ``-License`` in the license section.

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Matthew R. Becker



v3.6.15
====================

**Added:**

* Linter allows LicenseRef custom licenses.

**Removed:**

* Other is not a recognized license anymore.

* Deprecated SPDX license are not recognized anymore.

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Filipe Fernandes
* Matthew R. Becker
* Tim Snyder
* Dave Hirschfeld
* Nils Wentzell



v3.6.14
====================

**Fixed:**

* Package MANIFEST did not include the ``license_exceptions.txt`` file properly.

**Authors:**

* Matthew R. Becker



v3.6.13
====================

**Added:**

* Added code to validate feedstock tokens
* Added code to register FEEDSTOCK_TOKENS per CFEP-13
* Linter will now recommend SPDX expression for license entry

**Fixed:**

* Rerender use forge_config["recipe_dir"] instead of hardcoding "recipe" (#1254 & #1257)
* Fixed bug where BINSTAR_TOKEN's were not properly patched if they already
  existed for TravisCI.

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Tim Snyder



v3.6.12
====================

**Fixed:**

* Fix bug with conda 4.6.14 on Windows

**Authors:**

* Filipe Fernandes
* Dave Hirschfeld



v3.6.11
====================

**Added:**

* Added feature to upload the BINSTAR_TOKEN for travis-ci.com directly
  through the API

**Changed:**

* Updated the version of macOS image to 10.14 for Azure Pipelines.
* If conda-forge-pinning package has migrations installed, use those
  migration yaml files instead of the ones from the feedstock if the
  timestamp field match and remove if the migration yaml has a
  timestamp and there's no corresponding one in conda-forge-pinning
  which indicates that the migration is over.

**Deprecated:**

* Deprecated storing BINSTAR_TOKENs in the conda-forge.yml for travis

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Maksim Rakitin



v3.6.10
====================

**Fixed:**

* Fixed variant comparisons when the variant has a space

**Authors:**

* Isuru Fernando



v3.6.9
====================

**Added:**

* Add automerge github actions when rerendering
* Added the configuration file for the webservices github action

**Fixed:**

* Fix crash of linter when requirements contains packages that start with python in name

**Authors:**

* Isuru Fernando
* Matthew R Becker
* Matthew R. Becker
* Tim Werner



v3.6.8
====================

**Changed:**

* Changed the config name to remove * and space characters

**Authors:**

* Isuru Fernando
* Min RK



v3.6.7
====================

**Added:**

Non-noarch recipes shouldn't use version constraints on python and r-base.
The linter only checked for python, this PR addes the check for r-base.
* Added an option to skip adding webhooks

**Fixed:**

* Azure builds for OSX and Windows only attempt to upload if builds succeeded
  and the BINSTAR_TOKEN is available.

**Authors:**

* Isuru Fernando
* Mark Harfouche
* Natasha Pavlovikj



v3.6.6
====================

**Added:**

* ``conda smithy rerender`` now adds an automerge action if ``conda-forge.yml`` has ``bot: {automerge: True}`` set.
  This action merges PRs that are opened by the ``regro-cf-autotick-bot``, are passing, and have the ``[bot-automerge]``
  slug in the title.

**Fixed:**

* Fixed problems rendering the ``README.md`` for some ``Jinja2`` variables (#1215)

**Authors:**

* Christopher J. Wright
* Matthew R Becker
* Matthew R. Becker



v3.6.5
====================

**Added:**

* Added ``.gitignore`` entries when running ``ci-skeleton``.

**Fixed:**

* Fixed Jinja syntax error in ``ci-skeleton``.

**Authors:**

* Anthony Scopatz



v3.6.4
====================

**Added:**

* New ``conda smithy ci-skeleton`` subcommand that generates ``conda-forge.yml``
  and ``recipe/meta.yaml`` files for using conda-forge / conda-smithy as
  the CI configuration outside of configuration. Calling ``rerender`` after
  ``ci-skeleton`` will generate the configuration files. This is a great way to
  either bootstrap CI for a repo or continue to keep CI up-to-date.
  The ``recipe/meta.yaml`` that is generated is just a stub, and will need to
  be filled out for CI to properly build and test.

**Fixed:**

* Fix an issue with empty host
* Fix python lint for recipes with outputs



v3.6.3
====================

**Added:**

* Added a lint for common mistakes in python requirements
* Use shellcheck to lint ``*.sh`` files and provide findings as hints. Can be
  enabled via conda-forge.yaml (shellcheck: enabled: True), default (no entry)
  is False.
* Support aarch64 on travis-ci.com
* Support ppc64le on travis-ci.com
* Check that the current working directory is a feedstock before re-rendering.

**Changed:**

* Update travis feedstock registration to no longer generate anything for
travis-ci.org.



v3.6.2
====================

**Changed:**

* Changed the pipeline names in drone to less than 50 characters
* .scripts folder is also hidden in PR diffs

**Fixed:**

* Fixed a bug in configuring appveyor.yml



v3.6.1
====================

**Fixed:**

* Drone changed their service to no longer send the same environment variables. Changed to use ``$DRONE_WORKSPACE``.



v3.6.0
====================

**Added:**

* Ignore Drone CI files in GitHub diffs
* Run ``black --check`` on CI to verify code is formatted correctly

**Changed:**

* Platform independent files like `run_docker_build.sh` are moved to `.scripts` folder
* Standardize and test support for multiple docker images.
* refactored ``conda_smithy.lint_recipe.NEEDED_FAMILIES`` to top level so external projects can access
* Rerun ``black`` on the codebase.

**Fixed:**

* fix crash when host section was present but empty
* fix build-locally.py in skip_render by not attempting to chmod +x it
* ship conf file for black so everyone uses the same settings



v3.5.0
====================

**Added:**

* conda-smithy will remove the ``.github/CODEOWNERS`` file in case the recipe
  maintainers list is empty

**Changed:**

* Default windows provider was changed to azure.



v3.4.8
====================

**Fixed:**

* Don't make assumptions in ``conda_smithy/variant_algebra.py`` about the metadata



v3.4.7
====================

**Added:**

* Added a method to sync user in drone

**Changed:**

* Check that a project is registered if registering fails on drone
* Check that a project has the secret if adding secret fails on drone



v3.4.6
====================

**Added:**

* conda-smithy can now register packages on drone.io.  We plan on using this to help out with the aarch64
  architecture builds.

**Changed:**

* drone.io is now the default platform for aarch64 builds
* migrations folder changed from <feedstock_root>/migrations to <feedstock_root>/.ci_support/migrations

**Fixed:**

* Fix render_README crash when azure api returns 404



v3.4.5
====================

**Fixed:**

* YAML ``dump()`` now used ``pathlib.Path`` object.



v3.4.4
====================

**Fixed:**

* Updated conda-smithy to work with ruamel.yaml v0.16+.



v3.4.3
====================

**Changed:**

* In linting pins allow more than one space

**Fixed:**

* Don't lint setting build number



v3.4.2
====================

**Added:**

* Generating feedstocks with support for the linux-armv7l platform.
* test of the downgrade functionality of the new pinning system
* Mark generated files as generated so that github collapses them by deafult in diffs.
* The linter will now recomend fixes for malformed pins,
  suggesting a single space is inserted. For instance, both ``python>=3`` and
  ``python >= 3`` will ought to be ``python >=3``.
* New key ``upload_on_branch`` added to conda-forge.yml the value of which is checked
  against the current git branch and upload will be skipped if they are not equal.
  This is optional and an empty key skips the test.
* Added `CONDA_SMITHY_LOGLEVEL` environment variable to change verbosity
  of rendering. This can be either `debug` or `info`.

**Changed:**

* Add skip_render option to conda-forge.yaml. One could specify one or more filenames telling conda-smithy to skip making change on them. Files that could skip rendering include .gitignore, .gitattributes, README.md and LICENCE.txt.
* Reduced verbosity of rendering

**Fixed:**

* recipe-lint compatibility with ruamel.yaml 0.16
* Mock PY_VER in recipe check
* Fixed badge rendering in readme template.
* yum_requirements will now work on Travis based linux builds.
* requirements: update to conda-build>=3.18.3
* fix non-public conda import, use conda.exports
* requirements: replace pycrypto with pycryptodome



v3.4.1
====================

**Added:**

* license_file is required for GPL, MIT, BSD, APACHE, PSF

**Changed:**

* ``build-locally.py`` now uses ``python3`` even if ``python`` is ``python2`` (Python 3.6+ was already required)

**Removed:**

* Github issue, PR and contributing files are removed as they are in https://github.com/conda-forge/.github
* Support for python 2 Removed

**Fixed:**

* Fix configuring appveyor on repos starting with an underscore
* Fixed an issue where conda system variants could be used after rendering migrations.
* Fixed issue where only the last maintainer is review requested
* Unlicense is allowed
* Support newer ``shyaml`` versions by checking whether ``shyaml -h`` succeeds.



v3.4.0
====================

**Fixed:**

* bumped conda version check in CLI to 5.0 (from 4.7)



v3.3.7
====================

**Added:**

* Added codeowners file

**Fixed:**

* Fixed checking in .pyc files



v3.3.6
====================

**Fixed:**

* Indentation error in ``github.py``



v3.3.5
====================

**Added:**

* Added native aarch64 support for builds using Drone.io. This can be enabled by
  either using `provider: {linux_aarch64: drone}` or `provider: {linux_aarch64:
  native}` in the conda-forge.yml.

  Currently, drone has to be enabled manually as there is no automatic CI
  registration for repos.
* export CI env variable with CI provider name
* New ``build-locally.py`` script that is added to the root feedstock directory when
  ``conda smithy rerender`` is run. This script runs conda build locally. Currently
  it only fully supports running docker builds.
* print when adding new team to maintiners of feedstock

**Removed:**

* `docker.image` in conda-forge.yml is removed
* Removed the need for shyaml in CI env.

**Fixed:**

* removed empty lines causing current build status table to render as code
* build setup script overriding is now supported on azure too



v3.3.4
====================



v3.3.3
====================

**Added:**

* Added native ppc64le support to for travis-ci.  This can be enabled by either using
  `provider: {linux_ppc64le: travis}` or `provider: {linux_ppc64le: native}` in the conda-forge.yml.
  These will be the new default behavior going forward for ppc64le builds.  If native builds are not needed the
  qemu based builds on azure will continue to function as before.
* Added `DOCKER_IMAGE` variable to `run_docker_build.sh`

**Changed:**

* Fallback to default image in `run_docker_build.sh` if `shyaml` is not installed.

**Fixed:**

* Fixed badges for noarch builds using azure



v3.3.2
====================



v3.3.1
====================

**Fixed:**

* Use `config.instance_base_url` instead of `config.azure_team_instance` when creating new feedstocks



v3.3.0
====================

**Added:**

* Added a utility to retrieve the azure buildid.  This is needed to make badges for non-conda forge users.
* Added badges for azure ci builds.

**Changed:**

* Bumped up the maximum build time on azure to 6 hours!
* Switched default provider for osx and linux to be azure.
* ``conda-smithy regenerate`` now supports ``--check`` to see if regeneration can be performed
* Bumped the license year to 2019.
* Only suggest noarch in linting staged-recipes pull requests, not feedstocks.
  Refer to issues #1021, #1030, #1031. Linter is not checking all prerequisites for noarch.



v3.2.14
====================

**Added:**

* hint to suggest using python noarch, when the build requirements include pip and no compiler is specified.

**Fixed:**

* qemu activation fixed so that we can use sudo.



v3.2.13
====================

**Added:**

* Allow enabling aarch64 and ppc64le using default provider

**Changed:**

* Appveyor will now use the conda python3.x executable to run the fast-finish script.
* Azure windows builds are no longer silent.
* Azure build definition updating now works.

**Fixed:**

* yum_requirements will now work on azure based linux builds.



v3.2.12
====================

**Fixed:**

* Removed ``v`` from release that prevented conda-smithy version check from
  working properly.



v3.2.11
====================

**Fixed:**

* Secrets weren't getting passed to Azure properly.



v3.2.10
====================

**Changed:**

* Ran ``black`` on the codebase
* Added a few more always included keys.  These are required by the aarch64 migration.
These in particular are: ``cdt_arch``, ``cdt_name``,  ``BUILD``.



v3.2.9
====================



v3.2.8
====================

**Fixed:**

* conda-clean --lock does nothing.  Remove it.



v3.2.7
====================

**Fixed:**

* Fixed azure conditions for osx and win64



v3.2.6
====================

**Fixed:**

* Bugfix for uploading packages.



v3.2.5
====================

**Fixed:**

* Fixed docker image name from ``gcc7`` to ``comp7``.



v3.2.4
====================

**Fixed:**

* Fixed issue where azure was deleting linux configs for noarch packages.



v3.2.3
====================

**Added:**

* Added `conda-build` version to git commit message produced by `conda smithy regenerate`
* Made idle timeouts on travisci and circleci configurable.  To set this add to your `conda-forge-config.yml`

    .. code-block:: yaml

    idle_timeout_minutes: 30
None

* Added preliminary multiarch builds for aarch64 and ppc64le using qemu on azure.  This will be enabled by
means of a migrator at a later point in time.
Command line options are now available for the command `conda smithy register-ci`
to disable registration on a per-ci level. `--without-azure`, `--without-circle`,
`--without-travis`, and `--without-appveyor` can now be used in conjunction with
`conda smithy register-ci`.

**Changed:**

conda-build is now specified along side `conda-forge-ci-setup` installs so that it gets updated to the latest version available during each build.
* Moved NumFOCUS badge to "About conda-forge" section in the feedstock README.
* Removed ``branch2.0`` for the finding the fast-finish script, and changed it
  back to ``master``.

**Fixed:**

* Linter no longer fails if meta.yaml uses `os.sep`
* Fixed azure linux rendering caused by bad jinja rendering
* Linting only fails noarch recipes with selectors for host and runtime dependencies.



v3.2.2
====================

**Added:**

* recipe-maintainers can now be a conda-forge github team


**Fixed:**

* Azure fixed incorrect build setup
* Use setup_conda_rc for azure on windows
* Fixed creating feedstocks with conda-build 3.17.x
* Fixed bug in appveyor where custom channels are not used
* Added conda-forge when installing conda-forge-ci-setup to prevent Circle from changing channel priority




v3.2.1
====================

**Added:**

* Added support for rendering feedstock recipes for Azure pipelines.
  Presently this is enabled globally for all feedstocks going forward by default.
  Azure builds are configured to not publish artifacts to anaconda.org
* PR template asking for news entries
  (aka, I heard you like news, so I put a news item about adding news items into
  your news item, so you can add news while you add news)
* Feedstock maintainers are now listed in the README file.


**Removed:**

* Python 2.7 support has been dropped.  Conda-smithy now requires python >= 3.5.


**Fixed:**

* Fixes issue with Circle job definition where "filters are incompatible with
  workflows" when Linux is skipped. This was causing Linux jobs to be created
  and then fail on feedstocks where Linux and Circle were not needed.




v3.2.0
====================

**Changed:**

* updated toolchain lint to error


**Fixed:**

* The ``extra-admin-users`` flag can be None which is the default case. So, we have to check that before to make a loop on the entries of ``extra-admin-users`` list.
* The ``update-cb3`` command now handles ``toolchain3`` in the same way that
  ``toolchain`` is handled.




v3.1.12
====================

**Fixed:**

* fixed lint by checking that recipe-maintainers is an instance of
  ``collections.abc.Sequence``




v3.1.11
====================

**Changed:**

* Upgrade links to HTTPS and update link targets where necessary (#866)


**Removed:**

* Drop `vendored` package/directory. A remnant that is no longer used.


**Fixed:**

None

* Linter: packages without a `name` aren't actually in bioconda. (#872)
* Linter: handle new versions of `ruamel.yaml` appropriately instead of complaining about `expected to be a dictionary, but got a CommentedMap`. (#871)
* Fix missing newline in last line of generated readmes and add unit test for it (#864)




v3.1.10
====================

**Changed:**

- Change conda-smithy rerender text in PR template so that it is not invoked. (#858)


**Fixed:**

- Fix OrderedDict order not being kept (#854)




v3.1.9
====================

**Added:**

* Add merge_build_host: True #[win] for R packages in update-cb3


**Changed:**

* Package the tests




v3.1.8
====================

**Fixed:**

* Linter issue with multiple outputs and unexpected subsection checks




v3.1.7
====================

**Added:**

* Allow appveyor.image in conda-forge.yml to set the `appveyor image <https://www.appveyor.com/docs/build-environment/#choosing-image-for-your-builds>`_. (#808)
* Temporary travis user for adding repos  #815
* More verbose output for ``update-cb3``  #818
* ``.zip`` file support for ``update-cb3``  #832


**Changed:**

* Move noarch pip error to hint  #807
* Move biocona duplicate from error to hint  #809


**Fixed:**

- Fix OrderedDict representation in dumped yaml files (#820).
- Fix travis-ci API permission error (#812)
* Linter: recognize when tests are specified in the `outputs` section. (#830)




v3.1.6
====================

**Fixed:**

- Fix sorting of values of packages in `zip_keys` (#800)
- Fix `pin_run_as_build` inclusion for packages with `-` in their names (#796)
- Fix merging of configs when there are variants in outputs (#786, #798)
- Add `conda smithy update-cb3` command to update a recipe from conda-build v2 to v3 (##781)




v3.1.2
====================

**Added:**

None

* Require ``conda-forge-pinnings`` to run
None

* Update conda-build in the docker build script


**Changed:**

None

* Included package badges in a table
