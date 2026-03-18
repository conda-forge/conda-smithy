**Added:**

* <news item>

**Changed:**

* ``github_actions_labels`` field in ``conda_build_config.yaml`` can now mix Github-hosted and self-hosted runners. If absent, defaults to Github-hosted runners; this can be explicitly set with the ``default`` value too. (#2499)

**Deprecated:**

* ``github_actions.self_hosted`` configuration in ``conda-forge.yml`` doesn't have an effect anymore. Use ``github_actions_labels`` in ``conda_build_config.yaml`` to configure the ``runs-on`` field for each CI job. (#2499)

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
