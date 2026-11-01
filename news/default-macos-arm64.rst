**Changed:**

* ``conda-smithy init`` now enables native ``osx-arm64`` builds instead of
  ``osx-64`` for new feedstocks. Settings in a recipe's ``conda-forge.yml``
  override these defaults. To opt into Intel-only macOS builds, set
  ``provider.osx_64: azure`` and ``provider.osx_arm64: null``.
  Rerendering existing feedstocks retains their current platform defaults.
