"""Generate skeleton for using conda-forge CI configuration files outside of
a feedstock (i.e. a outside of a forge context). This enables people to use
conda-forge to run their CI without having to worry about how to set it up,
or keep it up-to-date.
"""
import os

from jinja2 import Environment, FileSystemLoader

from .configure_feedstock import make_jinja_env


def _generate_conda_forge_yml(env, recipe_directory="recipe"):
    """Generates the conda-forge.yml file."""


def generate(package_name="pkg", feedstock_directory=".", recipe_directory="recipe"):
    """Generates the skeleton."""
    env = make_jinja_env(feedstock_directory)


