**Added:**

* Added the ability to store conda build artifacts using the Github Actions provider. To enable, set `github_actions: {store_build_artifacts: true}` in conda-forge.yml.
* It is possible to set the lifetime of the Github Actions artifacts by setting the the `github_actions: {artifact_retention_days: 14}` setting in conda-forge.yml to the desired value. The default is 14 days.

**Changed:**

* Azure build artifacts for failed builds are now zipped before being uploaded, with some cache directories and the conda build/host/test environments removed, to make user download smaller and faster.
* Azure artifact names are now only shortened (uniquely) when necessary to keep the name below 80 characters.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Azure artifact names are now unique when a job needs to be restarted (#1430).
* Azure artifact uploads for failed builds that failed because of broken symbolic links have now been fixed.

**Security:**

* <news item>
