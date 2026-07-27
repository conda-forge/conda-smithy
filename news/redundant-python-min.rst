**Added:**

* New hint ``R-052``: recipes that redefine ``python_min`` (via ``context`` in v1 recipes or ``{% set %}`` in v0 recipes) to the same value as (or a lower value than) conda-forge's global pinning default are hinted to remove the redundant override. The global default is fetched from the pinning feedstock with the same cached, fail-quiet pattern used for ``hints.toml``.

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
