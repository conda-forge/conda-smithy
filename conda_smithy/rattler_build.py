from collections import OrderedDict
import fnmatch
import json
import os
import subprocess
import tempfile
from typing import Iterable
import yaml
from conda_build.variants import get_package_variants
from conda_build.metadata import MetaData as CondaMetaData, OPTIONALLY_ITERABLE_FIELDS
from conda_build.render import distribute_variants
from conda_build.config import get_or_merge_config


class MetaData(CondaMetaData):
    def __init__(self, path, recipe: dict, config=None, variant=None):
        self.config = get_or_merge_config(config, variant=variant)
        if os.path.isfile(path):
            self._meta_path = path
            self._meta_name = os.path.basename(path)
            self.path = os.path.dirname(path)
        else:
            self._meta_name = "recipe.yaml"
            # we should define our own find_recipe method
            # maybe to be insipired from conda_build
            self._meta_path = os.path.join(path, self._meta_name)
            self.path = os.path.dirname(self._meta_path)

        self.meta = recipe
        self.meta["about"] = recipe["recipe"].get("about", {})

        self.final = True
        self.undefined_jinja_vars = []

        self.requirements_path = os.path.join(self.path, "requirements.txt")

    @staticmethod
    def get_recipes(path, config, variants):
        platform_and_arch = f"{config.platform}-{config.arch}"

        try:
            with tempfile.NamedTemporaryFile(
                mode="w+"
            ) as outfile, tempfile.NamedTemporaryFile(mode="w") as variants_file:
                # dump variants in our variants that will be used to generate recipe
                try:
                    yaml.dump(variants, variants_file, default_flow_style=False)
                except Exception as e:
                    print(e)

                variants_path = variants_file.name
                output = subprocess.run(
                    [
                        "rattler-build",
                        "build",
                        "--render-only",
                        "-m",
                        variants_path,
                        "--recipe",
                        "recipe",
                        "--target-platform",
                        platform_and_arch,
                    ],
                    capture_output=False,
                    # shell=True,
                    stdout=outfile,
                )
                outfile.seek(0)
                # because currently rattler-build output just 2 jsons in *NOT* a list format
                # I need to preformat it

                content = outfile.read()

                formatted_content = content.replace("}\n{", ",")
                formatted_content = f"[{formatted_content}]"
                metadata = json.loads(formatted_content)

            return metadata if isinstance(metadata, list) else [metadata]

        except Exception as e:
            return []

    def get_used_vars(self, force_top_level=False, force_global=False):
        return list(self.meta["build_configuration"]["variant"].keys())

    def get_used_loop_vars(self, force_top_level=False, force_global=False):
        return set(self.meta["build_configuration"]["variant"].keys())

    def get_section(self, name):
        section = self.meta.get("recipe", {}).get(name)
        if name in OPTIONALLY_ITERABLE_FIELDS:
            if not section:
                return []
            elif isinstance(section, dict):
                return [section]
            elif not isinstance(section, list):
                raise ValueError(f"Expected {name} to be a list")
        else:
            if not section:
                return {}
            elif not isinstance(section, dict):
                raise ValueError(f"Expected {name} to be a dict")
        return section


def render_recipe(
    recipe_path,
    config=None,
    variants=None,
):
    """Returns a list of tuples, each consisting of

    (metadata-object, needs_download, needs_render_in_env)

    You get one tuple per variant.  Outputs are not factored in here (subpackages won't affect these
    results returned here.)
    """

    recipes = MetaData.get_recipes(recipe_path, config, variants)
    metadatas: list[MetaData] = []
    for recipe in recipes:
        metadata = MetaData(recipe_path, recipe, config=config)
        # just to have the same interface as conda_build
        metadatas.append(metadata)

    return metadatas


def render(
    recipe_path,
    config=None,
    variants=None,
    permit_unsatisfiable_variants=True,
    finalize=True,
    bypass_env_check=False,
    **kwargs,
):
    """Given path to a recipe, return the MetaData object(s) representing that recipe, with jinja2
       templates evaluated.

    Returns a list of (metadata, needs_download, needs_reparse in env) tuples"""

    config = get_or_merge_config(config, **kwargs)

    metadata_tuples = render_recipe(
        recipe_path,
        config=config,
        variants=variants,
    )

    for m in metadata_tuples:
        if not hasattr(m.config, "variants") or not m.config.variant:
            m.config.ignore_system_variants = True
            # TODO: should be variants.yml? or do we need to support both of them?

            if os.path.isfile(os.path.join(m.path, "conda_build_config.yaml")):
                m.config.variant_config_files = [
                    os.path.join(m.path, "conda_build_config.yaml")
                ]
            # TODO: still need to do an evaluation of selectors
            elif os.path.isfile(os.path.join(m.path, "variants.yaml")):
                m.config.variant_config_files = [os.path.join(m.path, "variants.yaml")]

            m.config.variants = get_package_variants(m, variants=variants)
            m.config.variant = m.config.variants[0]

            # These are always the full set.  just 'variants' is the one that gets
            #     used mostly, and can be reduced
            m.config.input_variants = m.config.variants

    return [(m, False, False) for m in metadata_tuples]
