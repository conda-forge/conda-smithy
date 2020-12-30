**Added:**

* Define Jinja functions ``stargroup()`` and ``endgroup()`` that provide a
  provider-agnostic way to group or fold log lines for quicker visual inspection.
  In principle, this only affects Linux and MacOS, since Windows pipelines
  use CI native steps. So far, only Azure and Travis support this. In the other
  providers a fallback ``echo <group name>`` statement is supplied.

**Changed:**

* `run_os_build.sh` had hardcoded handlers for Travis log folding. These have
  been replaced with now equivalent Jinja functions.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
