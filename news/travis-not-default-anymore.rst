**Added:**

* <news item>

**Changed:**

* Due to persistent problems with Travis CI, it is not the default provider for non-x64 architectures on linux anymore.
  Builds will be emulated on azure by default, though it is recommended to switch recipes to cross-compilation
  where possible, by adding the following to `conda-forge.yml` (and rerendering):
  ```
  build_platform:
    linux_aarch64: linux_64
    linux_ppc64le: linux_64
  ```

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
