**Added:**

* A lint for a malformed v1 section. ``tests`` written as a mapping or holding a
  bare string, a mapping in ``requirements`` that is not an ``if``/``then``
  conditional, and an ``if`` with no ``then`` are now reported instead of being
  read past silently.

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* The linter no longer raises on those sections. It used to lose every other lint
  for the recipe, so the author saw only that the linting service had failed.

**Security:**

* <news item>
