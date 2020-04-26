**Added:**

* Added new `pip-install`-based hooks for using a local copy of the
  `conda-forge-ci-setup` package.

**Changed:**

* Renamed the feedstock token output files to not munge "-feedstock" from
  the names.

* Bumped the default version of the `conda-forge-ci-setup` package to 3 to
  support the new output validation service.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Fixed bugs in tests for feedstock tokens.

**Security:**

* Added code to call the feedstock output validation service. You must have
  `conda_forge_output_validation` set to true in the `conda-forge.yml` to use
  this feature.
