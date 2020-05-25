**Added:**

* Use mamba to determine the latest version of ``conda-smithy`` and
  ``conda-forge-pinning`` if ``mamba`` is available. In case of an error, we
  will always silently fall back to using ``conda``.
