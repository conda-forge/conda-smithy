**Added:**

* For self-hosted github actions runs, a user can add custom labels
  by adding `github_actions_labels` yaml key in `recipe/conda_build_config.yaml`.
  The value `hosted` can be used for Microsoft hosted free runners
  and the value `self-hosted` can be used for the default self-hosted labels.

* `github_actions: timeout_minutes` option added to change the timeout in minutes.
  The default value is `360`.

* `github_actions: triggers` is a list of triggers which defaults to
  `push, pull_request` when not self-hosted and `push` when self-hosted.

* Added a `--cirun` argument to `conda-smithy ci-register` command to register
  `cirun` as a CI service. This makes `cirun` conda package a dependency of
  conda-smithy.

* Added support for `cirun` by generating a unique label when the self-hosted
  label starts with `cirun`.

* When a label is added that has the string with `gpu` or `GPU` for a self-hosted
  runner, the docker build will pass the GPUs to the docker instance.

**Changed:**

* `github_actions: cancel_in_progress` option added to cancel in progress runs.
  The default value was changed to `true`.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
