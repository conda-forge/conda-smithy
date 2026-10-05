**Added:**

* ``migrator_ts`` in migration files may now be an ISO 8601 date and time with an explicit UTC offset (e.g. ``2026-10-02T03:40:20Z``), in addition to seconds since the Unix epoch.
  Do not rewrite the ``migrator_ts`` of an existing migration, even into the other format, unless the migration is meant to restart: ISO 8601 timestamps are limited to microseconds, so the value may not survive the conversion, and a changed ``migrator_ts`` is a different migration.

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
