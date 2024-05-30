"""Generate skeleton for using conda-forge CI configuration files outside of
a feedstock (i.e. a outside of a forge context). This enables people to run
their CI without having to worry about how to set it up or keep it up-to-date,
by reusing the same tools that conda-forge uses for its infrastructure.
Note that your CI jobs will still execute under your organization, and not be
added to conda-forge's queue.
"""

from pathlib import Path
import sys

from .configure_feedstock import make_jinja_env


def _render_template(template_file, env, forge_dir, config):
    """Renders the template"""
    template_file_name = Path(template_file).name
    template = env.get_template(template_file_name + ".ci-skel.tmpl")
    target_fname = Path(forge_dir, template_file)
    print("Generating ", target_fname, file=sys.stderr)
    new_file_contents = template.render(**config)
    target_fname.parent.mkdir(parents=True, exist_ok=True)
    with open(target_fname, "w") as fh:
        fh.write(new_file_contents)


GITIGNORE_ADDITIONAL = """*.pyc
build_artifacts
"""


def _insert_into_gitignore(
    feedstock_directory=".",
    prefix="# conda smithy ci-skeleton start\n",
    suffix="# conda smithy ci-skeleton end\n",
):
    """Places gitignore contents into gitignore."""
    # get current contents
    fname = Path(feedstock_directory, ".gitignore")
    print("Updating ", fname.name)
    if fname.is_file():
        with open(fname, "r") as f:
            s = f.read()
        before, _, s = s.partition(prefix)
        _, _, after = s.partition(suffix)
    else:
        before = after = ""
        fname.parent.mkdir(parents=True, exist_ok=True)
    new = prefix + GITIGNORE_ADDITIONAL + suffix
    # write out the file
    with open(fname, "w") as f:
        f.write(before + new + after)
    return fname


def generate(
    package_name="pkg", feedstock_directory=".", recipe_directory="recipe"
):
    """Generates the CI skeleton."""
    forge_dir = Path(feedstock_directory).resolve()
    env = make_jinja_env(forge_dir)
    config = dict(
        package_name=package_name,
        feedstock_directory=feedstock_directory,
        recipe_directory=recipe_directory,
    )
    # render templates
    _render_template("conda-forge.yml", env, forge_dir, config)
    recipe_file_name = str(Path(recipe_directory, "meta.yaml"))
    _render_template(recipe_file_name, env, forge_dir, config)
    # update files which may exist with other content
    _insert_into_gitignore(feedstock_directory=feedstock_directory)
