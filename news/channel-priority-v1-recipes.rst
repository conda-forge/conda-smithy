**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Pass ``channel_priority`` from ``conda-forge.yml`` to ``rattler-build`` for v1 recipe builds. rattler-build uses its own resolver and does not read conda's condarc, so the setting was previously silently ignored on v1 recipes. The value is forwarded verbatim (only for rattler-build; conda-build already reads it from conda-forge.yml).

**Security:**

* <news item>
