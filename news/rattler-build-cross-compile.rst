**Fixed:**

* fix cross-compilation with rattler-build by setting `--target-platform=${HOST_PLATFORM}` and
  exporting `SYSTEM_VERSION_COMPAT=0` in the build script.
