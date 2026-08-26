**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* The ``pin_subpackage``/``pin_compatible`` lint now recovers the pinned package
  name correctly when that name is built from a variant variable. Such names
  cannot be resolved at lint time, and truncating the resulting template at its
  first space made valid v1 recipes lint, and reported other pins under a
  truncated name.

**Security:**

* <news item>
