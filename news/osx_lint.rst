**Added:**

* <news item>

**Changed:**

* The long-deprecated `MACOSX_DEPLOYMENT_TARGET` will not be taken into account anymore when rerendering a recipe (#2473).
* The linter now raises an error if `MACOSX_DEPLOYMENT_TARGET` is found in recipe configuration files (#2473).
* The linter will now also raise issues found in `conda_build_config.yaml` for v1 recipes (#2473).
* The linter will now raise if two different recipe configuration files are found (#2473).
* Issues related to `c_stdlib_version` / `MACOSX_SDK_VERSION` and `MACOSX_DEPLOYMENT_TARGET` have been
  moved to the conda-forge-specific part of the linter (c.f. `conda smithy lint --conda-forge`) (#2473).

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
