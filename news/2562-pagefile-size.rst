**Added:**

* ``workflow_settings.pagefile_size`` to set page file (swap file) size consistently across CI providers, on Linux and Windows. (#2562)

**Changed:**

* <news item>

**Deprecated:**

* ``azure.settings_linux.swapfile_size`` and ``azure.settings_win.variables.SET_PAGEFILE`` are deprecated in favor of ``workflow_settings.pagefile_size``. (#2562)

**Removed:**

* <news item>

**Fixed:**

* Swap file creation now works correctly on Namespace GHA runners. (#2577)

**Security:**

* <news item>
