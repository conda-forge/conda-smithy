**Added:**

* Added the opt-in ``github_actions.attest_packages`` option. When enabled, GitHub Actions
  creates one CEP-27 Sigstore attestation per uploaded package with sigstore-python, in the
  build job right after the upload, and stores it in the GitHub attestation API of the feedstock. The uploaded packages and the
  channel they are published to (the ``targetChannel`` of the attestation) are read from
  the ``attest-subjects-*.json`` files that conda-forge-ci-setup 4.34.0 or newer writes
  into the build folder. (#2749)

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
