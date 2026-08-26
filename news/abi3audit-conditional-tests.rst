**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* The ``hint_abi3_missing_abi3audit`` hint no longer fires when the
  ``abi3audit`` test is nested inside an ``if``/``then`` block, such as a test
  guarded by ``if: is_abi3``. The hint is also skipped for ``noarch: generic``
  outputs, which ship no extension module for ``abi3audit`` to check.

**Security:**

* <news item>
