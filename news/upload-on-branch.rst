**Added:**

* New key ``upload_on_branch`` added to conda-forge.yml the value of which is checked
  against the current git branch and upload will be skipped if they are not equal.
  This is optional and an empty key skips the test.
