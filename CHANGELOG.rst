=======================
conda-smithy Change Log
=======================

.. current developments

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




