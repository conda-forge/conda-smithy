**Added:**

* ``python build-locally.py --debug`` now works for ``rattler-build`` (v1
  ``recipe.yaml``) feedstocks. The Linux/Docker (``build_steps.sh``) and macOS
  (``run_osx_build.sh``) build scripts now invoke ``rattler-build debug setup``
  followed by ``rattler-build debug shell`` instead of printing
  "rattler-build currently doesn't support debug mode". This restores the
  interactive local-debugging workflow (the equivalent of ``conda debug``) that
  classic ``conda-build`` recipes already had. Requires ``rattler-build >=0.41``.
  (#2566)

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
