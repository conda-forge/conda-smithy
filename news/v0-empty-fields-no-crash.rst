**Added:**

* <news item>

**Changed:**

* An ``about`` item that is present but not text, such as a license written as a
  list, is now treated as missing rather than accepted.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* The linter no longer raises on a v0 field written with no value after the colon,
  or with a list or mapping where text was expected. It used to lose every other
  lint for the recipe, so the author saw only that the linting service had failed.

**Security:**

* <news item>
