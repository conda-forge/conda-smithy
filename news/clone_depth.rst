**Added:**

* Added `clone_depth` parameter for use in conda-forge.yml that sets the feedstock git clone depth for all providers. By default (`clone_depth: none`), current behavior is maintained by using the provider's default checkout/clone settings. A full clone with no depth limit can be specified by setting `clone_depth: 0`.

**Changed:**

* The `ci-skeleton` command now creates a default conda-forge.yml that sets `clone_depth: 0` for full depth clones on all providers. This default supports expected behavior when using `GIT_DESCRIBE_*` to set version and build numbers in the recipe by ensuring that tags are present. This effectively changes the default clone behavior for the Github Action and Travis providers, as all other providers do a full clone by default.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
