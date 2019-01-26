=======================
conda-smithy Change Log
=======================

.. current developments

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




