**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Variant keys that a recipe excludes from the hash of the build string (`build.force_ignore_keys` for conda-build recipes, `build.variant.ignore_keys` for rattler-build recipes) are now kept in the `.ci_support` files, so that recipes which use such a key (e.g. `cran_mirror` in a source URL) are rendered with its value at build time. (#2717)

**Security:**

* <news item>
