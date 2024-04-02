from collections import OrderedDict
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Dict, List, Optional
import yaml
from ruamel.yaml import YAML
from conda_build.metadata import MetaData as CondaMetaData, OPTIONALLY_ITERABLE_FIELDS
from conda_build.config import get_or_merge_config
from conda_build.variants import (
    filter_combined_spec_to_used_keys,
    get_default_variant,
    validate_spec,
    combine_specs,
)
from conda_build.metadata import get_selectors

from conda_smithy.rattler_build.loader import parse_recipe_config_file
from conda_smithy.rattler_build.utils import find_recipe


class MetaData(CondaMetaData):
    def __init__(
        self, path, rendered_recipe: Optional[dict] = None, config=None, variant=None
    ):
        self.config = get_or_merge_config(config, variant=variant)
        if os.path.isfile(path):
            self._meta_path = path
            self._meta_name = os.path.basename(path)
            self.path = os.path.dirname(path)
        else:
            self._meta_name = "recipe.yaml"
            self._meta_path = find_recipe(path)
            self.path = os.path.dirname(self._meta_path)

        self._rendered = False

        if not rendered_recipe:
            self.meta = self.parse_recipe()
            self.meta["about"] = self.meta.get("about", {})
        else:
            self.meta = rendered_recipe
            self._rendered = True
            self.meta["about"] = self.meta["recipe"].get("about", {})

        self.final = True
        self.undefined_jinja_vars = []

        self.requirements_path = os.path.join(self.path, "requirements.txt")

    def parse_recipe(self):
        yaml = YAML()
        with open(os.path.join(self.path, self._meta_name), "r") as recipe_yaml:
            return yaml.load(recipe_yaml)

    def render_recipes(self, variants) -> List[Dict]:
        platform_and_arch = f"{self.config.platform}-{self.config.arch}"

        try:
            with tempfile.NamedTemporaryFile(
                mode="w+"
            ) as outfile, tempfile.NamedTemporaryFile(mode="w") as variants_file:
                # dump variants in our variants that will be used to generate recipe
                if variants:
                    yaml.dump(variants, variants_file, default_flow_style=False)

                variants_path = variants_file.name
                
                # when rattler-build will be released, change the path to it
                _tmp_file_to_rattler_build = (
                    Path(__file__) / ".." / ".." / ".." / "rattler-build"
                )
                run_args = [
                    f"{_tmp_file_to_rattler_build.resolve()}",
                    "build",
                    "--render-only",
                    "--recipe",
                    self.path,
                    "--target-platform",
                    platform_and_arch,
                    "--build-platform",
                    platform_and_arch,
                ]

                if variants:
                    run_args.extend(["-m", variants_path])

                subprocess.run(
                    run_args,
                    check=True,
                    stdout=outfile,
                )

                outfile.seek(0)
                # because currently rattler-build output just 2 jsons in *NOT* a list format
                # I need to preformat it

                content = outfile.read()
                # formatted_content = content.replace("}\n{", ",")
                # formatted_content = f"[{formatted_content}]"
                metadata = json.loads(content)
            return metadata if isinstance(metadata, list) else [metadata]

        except Exception as e:
            raise e

    def get_used_vars(self, force_top_level=False, force_global=False):
        if "build_configuration" not in self.meta:
            # it could be that we skip build for this platform
            # so no variants have been discovered
            # return empty
            return set()

        used_vars = [
            var.replace("-", "_")
            for var in self.meta["build_configuration"]["variant"].keys()
        ]

        # in conda-build target-platform is not returned as part of yaml vars
        # so it's included manually
        # in our case it is always present in build_configuration.variant
        # so we remove it when it's noarch
        if "target_platform" in self.config.variant and self.noarch:
            used_vars.remove("target_platform")

        return set(used_vars)

    def get_used_variant(self) -> dict:
        if "build_configuration" not in self.meta:
            # it could be that we skip build for this platform
            # so no variants have been discovered
            # return empty
            return {}

        used_variant = dict(self.meta["build_configuration"]["variant"])

        used_variant_key_normalized = {}

        for key, value in used_variant.items():
            normalized_key = key.replace("-", "_")
            used_variant_key_normalized[normalized_key] = value

        # in conda-build target-platform is not returned as part of yaml vars
        # so it's included manually
        # in our case it is always present in build_configuration.variant
        # so we remove it when it's noarch
        if "target_platform" in used_variant_key_normalized and self.noarch:
            used_variant_key_normalized.pop("target_platform")

        return used_variant_key_normalized

    def get_used_loop_vars(self, force_top_level=False, force_global=False):
        return self.get_used_vars(force_top_level, force_global)

    def get_section(self, name):
        if not self._rendered:
            section = self.meta.get(name)
        else:
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
) -> List[MetaData]:
    """Returns a list of tuples, each consisting of

    (metadata-object, needs_download, needs_render_in_env)

    You get one tuple per variant.  Outputs are not factored in here (subpackages won't affect these
    results returned here.)
    """

    metadata = MetaData(recipe_path, config=config)
    recipes = metadata.render_recipes(variants)

    metadatas: list[MetaData] = []
    if not recipes:
        return [metadata]

    for recipe in recipes:
        metadata = MetaData(recipe_path, rendered_recipe=recipe, config=config)
        # just to have the same interface as conda_build
        metadatas.append(metadata)

    return metadatas


def render(
    recipe_path,
    config=None,
    variants=None,
    **kwargs,
):
    """Given path to a recipe, return the MetaData object(s) representing that recipe, with jinja2
       templates evaluated.

    Returns a list of (metadata, needs_download, needs_reparse in env) tuples"""

    config = get_or_merge_config(config, **kwargs)

    arg = recipe_path
    if os.path.isfile(arg):
        if arg.endswith(".yaml"):
            recipe_dir = os.path.dirname(arg)
        else:
            raise ValueError("Recipe don't have a valid extension: %s" % arg)
    else:
        recipe_dir = os.path.abspath(arg)

    metadata_tuples = render_recipe(
        recipe_dir,
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

            # import pdb; pdb.set_trace()

            # we can't reuse get_package_variants from conda-build
            # so we ask directly metadata to give us used variant
            # and by iterate the variants itself, we remove unused keys

            # passed_variant = dict(variants) if variants else {}

            used_variant = m.get_used_variant()

            # for used_variant_key, used_variant_value in used_var.items():
            #     if used_variant_key in passed_variant:
            #         passed_variant[used_variant_key] = [used_variant_value]

            package_variants = rattler_get_package_variants(m, variants=variants)

            m.config.variants = package_variants[:]

            # we need to discard variants that we don't use
            for pkg_variant in package_variants[:]:
                for used_variant_key, used_variant_value in used_variant.items():
                    if used_variant_key in pkg_variant:
                        if pkg_variant[used_variant_key] != used_variant_value:
                            if pkg_variant in package_variants:
                                package_variants.remove(pkg_variant)

            m.config.variant = package_variants[0]

            # These are always the full set.  just 'variants' is the one that gets
            #     used mostly, and can be reduced

            m.config.input_variants = m.config.variants
            m.config.variants = package_variants

    return [(m, False, False) for m in metadata_tuples]


def get_package_combined_spec(recipedir_or_metadata, config, variants=None):
    # outputs a tuple of (combined_spec_dict_of_lists, used_spec_file_dict)
    #
    # The output of this function is order preserving, unlike get_package_variants

    config = recipedir_or_metadata.config
    namespace = get_selectors(config)
    variants_paths = config.variant_config_files

    specs = OrderedDict(internal_defaults=get_default_variant(config))

    for variant_path in variants_paths:
        specs[variant_path] = parse_recipe_config_file(variant_path, namespace)

    # this is the override of the variants from files and args with values from CLI or env vars
    if hasattr(config, "variant") and config.variant:
        specs["config.variant"] = config.variant
    if variants:
        specs["argument_variants"] = variants

    for f, spec in specs.items():
        validate_spec(f, spec)

    # this merges each of the specs, providing a debug message when a given setting is overridden
    #      by a later spec
    combined_spec = combine_specs(specs, log_output=config.verbose)

    return combined_spec, specs


def rattler_get_package_variants(recipedir_or_metadata, config=None, variants=None):
    combined_spec, specs = get_package_combined_spec(
        recipedir_or_metadata, config=config, variants=variants
    )
    return filter_combined_spec_to_used_keys(combined_spec, specs=specs)
