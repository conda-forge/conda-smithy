**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

Fixed a bug in run_docker_build.sh when finding the value of FEEDSTOCK_ROOT.
In some cases the cd command had output to stdout which was included in
FEEDSTOCK_ROOT. Now the value is computed as for THISDIR in the same script,
with the output of cd redirected to /dev/null.

**Security:**

* <news item>
