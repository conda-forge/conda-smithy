**Added:**

* The linter will now warn if allowed ``pyXY`` selectors are used (e.g. ``py27``, ``py34``, ``py35``, ``py36``). For other versions (e.g. Python 3.8 would be ``py38``), these selectors are *silently ignored*  by ``conda-build``, so the linter will throw an error to prevent situations that might be tricky to debug. We recommend using ``py`` and integer comparison instead. Note that ``py2k`` and ``py3k`` are still allowed.

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
