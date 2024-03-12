**Added:**

* New JSON schema for ``conda-forge.yaml``. A Pydantic model is used to dynamically generate both a YAML document with the default values and the JSON schema itself. (#1756)
* Included ``jsonschema`` and ``pydantic`` as dependencies into the ``environment.yml``. (#1756)

**Changed:**

* Included extra ``jsonschema`` validation for conda-forge.yaml, under ``configure_feedstock``. (#1756)
* Moved legacy checks of old_file and providers into a new auxiliary ``_legacy_compatibility_checks`` function. (#1756)

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
