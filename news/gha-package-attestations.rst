**Added:**

* Added the opt-in ``github_actions.attest_packages`` option. When enabled, a single job at
  the end of the GitHub Actions workflow creates one CEP-27 Sigstore attestation per uploaded
  package and stores it in the GitHub attestation API of the feedstock. The packages and the
  channel they are published to (the ``targetChannel`` of the attestation) come from the
  ``attest-subjects-*.json`` files that conda-forge-ci-setup 4.34.0 or newer writes into the
  build folder, and the signing is done by its ``attest_packages`` command. (#2749)

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
