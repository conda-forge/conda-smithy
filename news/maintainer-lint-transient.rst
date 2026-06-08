**Added:**

* <news item>

**Changed:**

* The recipe-maintainer existence lint no longer treats a transient GitHub
  failure (rate limit, server error, or network error) as "maintainer does not
  exist". Such checks are now retried and, if still inconclusive, the lint fails
  with a message (``CF-008``) asking for the linter to be re-run, instead of
  producing a false-positive "does not exist" lint.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Fixed false-positive ``Recipe maintainer "..." does not exist`` lints caused
  by unauthenticated GitHub rate limiting during linting.

**Security:**

* <news item>
