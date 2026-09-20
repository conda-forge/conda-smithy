**Added:**

* Native ``linux_riscv64`` builds can now be rendered on GitHub Actions using
  the usual interface (``provider: {linux_riscv64: X}`` where ``X`` is
  ``github_actions``, ``default`` or ``native``) in ``conda-forge.yml``. Jobs run
  on RISC-V hardware (``ubuntu-24.04-riscv``) provided by the RISE RISC-V
  runners GitHub App. (#2686)

**Changed:**

* Requesting ``provider: {<platform>: native}`` for a platform without a native
  CI provider now raises an error instead of being silently ignored. (#2686)

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
