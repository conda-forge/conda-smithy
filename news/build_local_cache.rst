**Changed:**

* build_locally now creates conda's shared package cache outside the container,
  so repeated builds of the same recipe do not need to redownload packages.
