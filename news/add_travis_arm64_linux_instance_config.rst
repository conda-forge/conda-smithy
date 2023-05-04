**Added:**

* Added `travis: {linux_aarch64: {type: arm64-graviton2}` to specify the use of Graviton 2 for AArch64 Linux builds On Travis CI, which according to Amazon should make builds up to two-times faster than the Travis default. Optionally you can specify an instance size, `travis: {linux_aarch64: {type: arm64-graviton2, size: large}`,  this should allow us to build packages that currently timeout or results in OOM errors. Compared to the default medium instance, the large doubles vCPUs from 2 to 4 and increases RAM from 7.5 GB to ~16GB.

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
