**Added:**

* Added `travis: {linux_aarch64: {type: arm64-graviton2}` to specify the use of an Amazon Graviton 2 VM for Linux AArch64 builds on Travis CI, which according to Amazon should make builds up to two-times faster than the Travis default. To specify an instance size, use `travis: {linux_aarch64: {type: arm64-graviton2, size: large}`, this should help us build packages that may otherwise timeout or result in OOM errors. Compared to the default 'medium' instance, the 'large' doubles vCPUs from 2 to 4 and increases RAM from 7.5GB to ~16GB.

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
