**Deprecated:**

* We have deprecated the usage of Travis CI for any platforms but linux_aarch64, linux_ppc64le, or
  linux_s390x. Conda-smithy will raise a RuntimeError if one attempts to render a recipe for a different platform.
