**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* ``MACOSX_DEPLOYMENT_TARGET`` and ``MACOSX_SDK_VERSION`` are now zipped with
  ``c_stdlib_version`` when a feedstock builds more than one macOS deployment
  target tier. Both keys are derived per variant from ``c_stdlib_version``, but
  that relationship was not recorded in ``zip_keys``, so every rendered
  ``.ci_support/osx_*`` file listed all of the tiers' values instead of its own.
  Single-tier feedstocks, which are nearly all of them, render unchanged.

**Security:**

* <news item>
