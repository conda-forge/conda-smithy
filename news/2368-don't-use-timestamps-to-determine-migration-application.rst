**Added:**

* <news item>

**Changed:**

* Avoid using migration timestamps to determine whether migrations should be applied. The logic for ``use_local`` and ``migration_number`` remains unchanged, but migrations are now uniformly applied based on the name of the migrator file, and timestamps are only used to order the application of migrators (#2368).

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
