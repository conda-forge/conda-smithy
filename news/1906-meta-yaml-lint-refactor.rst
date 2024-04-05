**Added:**

* <news item>

**Changed:**

* the meta.yaml linting logic is now split in different linters which are located in ``linters_meta_yaml``
* the meta.yaml linting logic now uses a more type-safe way to access individual sections and subsections of the meta.yaml file

**Deprecated:**

* module-level constants in ``lint_recipe``: ``str_type, FIELDS, EXPECTED_SECTION_ORDER, REQUIREMENTS_ORDER, TEST_KEYS TEST_FILES, NEEDED_FAMILIES, sel_pat, jinja_pat, JINJA_VAR_PAT`` (see the deprecation warnings in the module for more information)
* module-level functions in `lint_recipe`: ``find_local_config_file, get_list_section, get_section, is_jinja_line, is_selector_line, jinja_lines, lint_about_contents, lint_section_order, selector_lines`` (see the deprecation warnings in the module for more information)
* ``lint_recipe.lintify_meta_yaml`` (use ``lint_meta_yaml`` instead, signature changed)

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
