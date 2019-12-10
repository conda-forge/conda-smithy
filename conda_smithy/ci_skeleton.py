"""Generate skeleton for using conda-forge CI configuration files outside of
a feedstock (i.e. a outside of a forge context). This enables people to use
conda-forge to run their CI without having to worry about how to set it up,
or keep it up-to-date.
"""
import os
import sys

from jinja2 import Environment, FileSystemLoader

from .configure_feedstock import make_jinja_env


def _render_template(template_file, env, forge_dir, config):
    """Renders the template"""
    template = env.get_template(
        os.path.basename(template_file) + ".ci-skel.tmpl"
    )
    target_fname = os.path.join(forge_dir, template_file)
    print("Generating " + target_fname, file=sys.stderr)
    new_file_contents = template.render(**config)
    os.makedirs(os.path.dirname(target_fname), exist_ok=True)
    with open(target_fname, "w") as fh:
        fh.write(new_file_contents)


def generate(
    package_name="pkg", feedstock_directory=".", recipe_directory="recipe"
):
    """Generates the CI skeleton."""
    forge_dir = os.path.abspath(feedstock_directory)
    env = make_jinja_env(forge_dir)
    config = dict(
        package_name=package_name,
        feedstock_directory=feedstock_directory,
        recipe_directory=recipe_directory,
    )
    # render templates
    _render_template("conda-forge.yml", env, forge_dir, config)
    _render_template(
        os.path.join(recipe_directory, "meta.yaml"), env, forge_dir, config
    )
