**Added:**

* Additional secrets can be passed to the build by setting `secrets: ["BINSTAR_TOKEN", "ANOTHER_SECRET"]`
  in `conda-forge.yml`. These secrets are read from the CI configuration and
  then exposed as environment variables. To make them visible to build scripts,
  they need to be whitelisted in `build.script_env` of `meta.yaml`.
  This can, e.g., be used to collect coverage statistics during a build or test
  and upload them to sites such as coveralls.

**Security:**

* Added --suppress-variables so that CI secrets cannot be leaked by conda-build into CI logs.

