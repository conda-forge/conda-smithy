**Added:**

* Added support for self-hosted github actions runners

  In conda-forge.yml, add ``github_actions: self_hosted: true`` to
  enable self-hosted github actions runner. Note that self-hosted
  runners are currently configured to run only on push events
  and pull requests will not be built.

* Allow multiple providers per platform

  In conda-forge.yml, add ``provider: <platform>: ['ci_1', 'ci_2']``
  to configure multiple providers per platform.

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
