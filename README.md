Overview
--------

`conda-smithy` is a tool for combining a conda recipe with configurations to build using freely hosted CI services into a single repository, also known as a feedstock.
`conda-smithy` is still a work-in-progress, but when complete, `conda-smithy` will:

+ Create a git repo.
+ Register the repo on github and push it.
+ Connect the repo to the CI services travis-ci.org, appveyor.com, circleci.com

Installation
------------

Clone this repo then `python setup.py install`.

Setup
-----

You need a token from github, travis-ci.org, appveyor.com and circleci.com to try out `conda-smithy`. If you need help getting tokens please ask on the [conda-forge google group](https://groups.google.com/forum/?hl=en#!forum/conda-forge).

You should be able to test parts of `conda-smithy` with whatever tokens you have.
For example, you should be able to `conda smithy github-create` without the CI service tokens.

Making a new feedstock
----------------------

1. **Make the feedstock repo:** `conda smithy init
<directory_of_conda_recipe>`.     For a recipe called `foo`, this creates a
directory called `foo-feedstock`, populates it with CI setup skeletons, and
initializes it as a git repo.
2. **Create a github repo:** `conda smithy github-create --organization conda-forge foo-feedstock`.
This requires a github token. You can try it out with a github user account
instead of an organization by replacing the organization argument with
`--user github_user_name`.
3. **Register the feedstock with CI services:** 
`conda smithy register-feedstock-ci --organization conda-forge foo-feedstock`.
This requires tokens for the CI services. You can give the name of a user instead
of organization with `--user github_user_name`.

Running a build
---------------

When everything is configured you can trigger a build with a push to the feedstock repo on github.
