import os

import ruamel.yaml


EXPECTED_SECTION_ORDER = ['package', 'source', 'build', 'requirements', 'test', 'app', 'about', 'extra']


def lintify(meta):
    lints = []

    major_sections = list(meta.keys())

    # 1: Top level meta.yaml keys should have a specific order.
    section_order_sorted = sorted(major_sections, key=EXPECTED_SECTION_ORDER.index)
    if major_sections != section_order_sorted:
        lints.append('The top level meta keys are in an unexpected order. Expecting {}.'.format(section_order_sorted))

    # 2: The about section should have a home, license and summary.
    for about_item in ['home', 'license', 'summary']:
        about_section = meta.get('about', {}) or {}
        # if the section doesn't exist, or is just empty, lint it.
        if not about_section.get(about_item, ''):
            lints.append('The {} item is expected in the about section.'.format(about_item))

    # 3: The recipe should have some maintainers.
    extra_section = meta.get('extra', {}) or {}
    if not extra_section.get('recipe-maintainers', []):
        lints.append('The recipe could do with some maintainers listed in the "extra/recipe-maintainers" section.')

    # 4: The recipe should have some tests.
    if 'test' not in major_sections:
        lints.append('The recipe must have some tests.')

    return lints


def main(recipe_dir):
    recipe_dir = os.path.abspath(recipe_dir)
    recipe_meta = os.path.join(recipe_dir, 'meta.yaml')
    if not os.path.exists(recipe_dir):
        raise IOError('Feedstock has no recipe/meta.yaml.')
    with open(recipe_meta, 'r') as fh:
        meta = ruamel.yaml.load(fh, ruamel.yaml.RoundTripLoader)
    results = lintify(meta)
    return results
