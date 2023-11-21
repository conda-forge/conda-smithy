**Added:**

* New conda-forge pydantic schema for ``conda-forge.yaml``, includes a generate default forge yaml and json schema dynamically from the pydantic model
* Included ``jsonschema``and ``pydantic`` as dependencies into the ``environment.yml``

**Changed:**

* Included extra ``jsonschema`` validation for forge yaml, under ``configure_feedstock``
* Moved legacy checks of old_file and providers into a new  auxiliary ``_legacy_compatibility_checks`` function

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
