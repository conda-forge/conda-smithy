=======================
conda-smithy Change Log
=======================

.. current developments

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




