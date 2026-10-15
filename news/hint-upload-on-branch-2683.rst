**Added:**

* Added a hint if ``upload_on_branch`` is not set in ``conda-forge.yml``. This hint
  will become a lint on or after ``conda-smithy`` version ``2026.11.15``. (#2683)

**Changed:**

* Changed test suite to skip redundant and slow tests for file permissions. (#2683)

**Deprecated:**

* Deprecated uploads on all branches via having ``upload_on_branch`` unset. Starting with
  versions on or after ``2026.11.15``, ``conda-smithy`` will lint if ``upload_on_branch``
  is not set. (#2683)

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
