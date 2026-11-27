**Added:**

* Added the opt-in ``github_actions.attest_packages`` option. When enabled, conda-forge-ci-setup
  4.34.0 or newer signs one CEP-27 Sigstore attestation per package right after it is uploaded to
  conda-forge, and stores it in the GitHub attestation API of the feedstock. The workflow gets the
  ``id-token: write`` and ``attestations: write`` permissions, and the OIDC variables and
  ``GITHUB_TOKEN`` are passed to the build (not for pull requests).

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
