**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* CI integrations for Appveyor, CircleCI, Cirrus Runners, Drone, Travis, and Woodpecker are now considered deprecated. All functions and functionality regarding these obsolete CI providers (see below) will be removed in 26.10. (#2627 via #2633)

    * ``conda_smithy.anaconda_token_rotation.rotate_token_in_azure()``
    * ``conda_smithy.anaconda_token_rotation.rotate_token_in_circle()``
    * ``conda_smithy.anaconda_token_rotation.rotate_token_in_circle()``
    * ``conda_smithy.anaconda_token_rotation.rotate_token_in_drone()``
    * ``conda_smithy.ci_register.add_project_to_appveyor()``
    * ``conda_smithy.ci_register.add_project_to_azure()``
    * ``conda_smithy.ci_register.add_project_to_drone()``
    * ``conda_smithy.ci_register.add_project_to_travis()``
    * ``conda_smithy.ci_register.add_token_to_circle()``
    * ``conda_smithy.ci_register.add_token_to_drone()``
    * ``conda_smithy.ci_register.add_token_to_travis()``
    * ``conda_smithy.ci_register.appveyor_configure()``
    * ``conda_smithy.ci_register.appveyor_encrypt_binstar_token()``
    * ``conda_smithy.ci_register.disable_cirrus_runners_app()``
    * ``conda_smithy.ci_register.drone_sync()``
    * ``conda_smithy.ci_register.enable_cirrus_runners_app()``
    * ``conda_smithy.ci_register.regenerate_drone_webhooks()``
    * ``conda_smithy.ci_register.travis_cleanup()``
    * ``conda_smithy.ci_register.travis_configure()``
    * ``conda_smithy.ci_register.travis_encrypt_binstar_token()``
    * ``conda_smithy.ci_register.travis_get_repo_info()``
    * ``conda_smithy.ci_register.travis_headers()``
    * ``conda_smithy.ci_register.travis_repo_writable()``
    * ``conda_smithy.ci_register.travis_token_update_conda_forge_config()``
    * ``conda_smithy.ci_register.travis_wait_until_synced()``
    * ``conda_smithy.configure_feedstock.render_appveyor()``
    * ``conda_smithy.configure_feedstock.render_circle()``
    * ``conda_smithy.configure_feedstock.render_drone()``
    * ``conda_smithy.configure_feedstock.render_travis()``
    * ``conda_smithy.configure_feedstock.render_woodpecker()``
    * ``conda_smithy.feedstock_tokens.add_feedstock_token_to_circle()``
    * ``conda_smithy.feedstock_tokens.add_feedstock_token_to_drone()``
    * ``conda_smithy.feedstock_tokens.add_feedstock_token_to_travis()``
    * Some entries in ``conda_smithy.schema.CIservices`` are now part of ``.DeprecatedCIservices``

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
