# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import io
import itertools
import os
import re
import github

import jinja2
import ruamel.yaml

from conda_build.metadata import (ensure_valid_license_family,
                                  FIELDS as cbfields)
import copy

FIELDS = copy.deepcopy(cbfields)

# Just in case 'extra' moves into conda_build
if 'extra' not in FIELDS.keys():
    FIELDS['extra'] = []

FIELDS['extra'].append('recipe-maintainers')

EXPECTED_SECTION_ORDER = ['package', 'source', 'build', 'requirements',
                          'test', 'app', 'about', 'extra']

REQUIREMENTS_ORDER = ['build', 'run']

TEST_KEYS = {'imports', 'commands'}


class NullUndefined(jinja2.Undefined):
    def __unicode__(self):
        return self._undefined_name

    def __getattr__(self, name):
        return '{}.{}'.format(self, name)

    def __getitem__(self, name):
        return '{}["{}"]'.format(self, name)


def get_section(parent, name, lints):
    section = parent.get(name, {})
    if not isinstance(section, dict):
        lints.append('The "{}" section was expected to be a dictionary, but '
                     'got a {}.'.format(name, type(section).__name__))
        section = {}
    return section


def lintify(meta, recipe_dir=None, conda_forge=False):
    lints = []
    major_sections = list(meta.keys())

    # If the recipe_dir exists (no guarantee within this function) , we can
    # find the meta.yaml within it.
    meta_fname = os.path.join(recipe_dir or '', 'meta.yaml')

    source_section = get_section(meta, 'source', lints)
    build_section = get_section(meta, 'build', lints)
    requirements_section = get_section(meta, 'requirements', lints)
    test_section = get_section(meta, 'test', lints)
    about_section = get_section(meta, 'about', lints)
    extra_section = get_section(meta, 'extra', lints)
    package_section = get_section(meta, 'package', lints)

    # 1: Top level meta.yaml keys should have a specific order.
    section_order_sorted = sorted(major_sections,
                                  key=EXPECTED_SECTION_ORDER.index)
    if major_sections != section_order_sorted:
        section_order_sorted_str = map(lambda s: "'%s'" % s,
                                       section_order_sorted)
        section_order_sorted_str = ", ".join(section_order_sorted_str)
        section_order_sorted_str = "[" + section_order_sorted_str + "]"
        lints.append('The top level meta keys are in an unexpected order. '
                     'Expecting {}.'.format(section_order_sorted_str))

    # 2: The about section should have a home, license and summary.
    for about_item in ['home', 'license', 'summary']:
        # if the section doesn't exist, or is just empty, lint it.
        if not about_section.get(about_item, ''):
            lints.append('The {} item is expected in the about section.'
                         ''.format(about_item))

    # 3a: The recipe should have some maintainers.
    if not extra_section.get('recipe-maintainers', []):
        lints.append('The recipe could do with some maintainers listed in '
                     'the `extra/recipe-maintainers` section.')

    # 3b: Maintainers should be a list
    if not isinstance(extra_section.get('recipe-maintainers', []), list):
        lints.append('Recipe maintainers should be a json list.')

    # 4: The recipe should have some tests.
    if not any(key in TEST_KEYS for key in test_section):
        test_files = ['run_test.py', 'run_test.sh', 'run_test.bat',
                      'run_test.pl']
        a_test_file_exists = (recipe_dir is not None and
                              any(os.path.exists(os.path.join(recipe_dir,
                                                              test_file))
                                  for test_file in test_files))
        if not a_test_file_exists:
            lints.append('The recipe must have some tests.')

    # 5: License cannot be 'unknown.'
    license = about_section.get('license', '').lower()
    if 'unknown' == license.strip():
        lints.append('The recipe license cannot be unknown.')

    # 6: Selectors should be in a tidy form.
    if recipe_dir is not None and os.path.exists(meta_fname):
        bad_selectors = []
        bad_lines = []
        # Good selectors look like ".*\s\s#\s[...]"
        good_selectors_pat = re.compile(r'(.+?)\s{2,}#\s\[(.+)\](?(2).*)$')
        with io.open(meta_fname, 'rt') as fh:
            for selector_line, line_number in selector_lines(fh):
                if not good_selectors_pat.match(selector_line):
                    bad_selectors.append(selector_line)
                    bad_lines.append(line_number)
        if bad_selectors:
            lints.append('Selectors are suggested to take a '
                         '``<two spaces>#<one space>[<expression>]`` form.'
                         'see lines {}'.format(bad_lines))

    # 7: The build section should have a build number.
    if build_section.get('number', None) is None:
        lints.append('The recipe must have a `build/number` section.')

    # 8: The build section should be before the run section in requirements.
    requirements_order_sorted = sorted(requirements_section,
                                       key=REQUIREMENTS_ORDER.index)
    if list(requirements_section.keys()) != requirements_order_sorted:
        lints.append('The `requirements/build` section should be defined '
                     'before the `requirements/run` section.')

    # 9: Files downloaded should have a hash.
    if ('url' in source_section and
            not ({'sha1', 'sha256', 'md5'} & set(source_section.keys()))):
        lints.append('When defining a source/url please add a sha256, sha1 '
                     'or md5 checksum (sha256 preferably).')

    # 10: License should not include the word 'license'.
    license = about_section.get('license', '').lower()
    if 'license' in license.lower():
        lints.append('The recipe `license` should not include the word '
                     '"License".')

    # 11: There should be one empty line at the end of the file.
    if recipe_dir is not None and os.path.exists(meta_fname):
        with io.open(meta_fname, 'r') as f:
            lines = f.read().split('\n')
        # Count the number of empty lines from the end of the file
        empty_lines = itertools.takewhile(lambda x: x == '', reversed(lines))
        end_empty_lines_count = len(list(empty_lines))
        if end_empty_lines_count > 1:
            lints.append('There are {} too many lines.  '
                         'There should be one empty line at the end of the '
                         'file.'.format(end_empty_lines_count - 1))
        elif end_empty_lines_count < 1:
            lints.append('There are too few lines.  There should be one empty '
                         'line at the end of the file.')

    # 12: License family must be valid (conda-build checks for that)
    try:
        ensure_valid_license_family(meta)
    except RuntimeError as e:
        lints.append(str(e))

    # 13: Check that the recipe name is valid
    recipe_name = package_section.get('name', '').strip()
    if re.match('^[a-z0-9_\-.]+$', recipe_name) is None:
        lints.append('Recipe name has invalid characters. only lowercase alpha, numeric, '
                     'underscores, hyphens and dots allowed')

    # 14: Run conda-forge specific lints
    if conda_forge:
        run_conda_forge_lints(meta, recipe_dir, lints)

    # 15: Check if we are using legacy patterns
    build_reqs = requirements_section.get('build', None)
    if build_reqs and ('numpy x.x' in build_reqs):
        lints.append('Using pinned numpy packages is a deprecated pattern.  Consider '
                     'using the method outlined '
                     '[here](https://conda-forge.org/docs/meta.html#building-against-numpy).')

    # 16: Subheaders should be in the allowed subheadings
    for section in major_sections:
        expected_subsections = FIELDS.get(section, [])
        for subsection in get_section(meta, section, lints):
            if subsection not in expected_subsections:
                lints.append('The {} section contained an unexpected '
                             'subsection name. {} is not a valid subsection'
                             ' name.'.format(section, subsection))

    return lints


def run_conda_forge_lints(meta, recipe_dir, lints):
    gh = github.Github(os.environ['GH_TOKEN'])
    package_section = get_section(meta, 'package', lints)
    extra_section = get_section(meta, 'extra', lints)
    recipe_dirname = os.path.basename(recipe_dir) if recipe_dir else 'recipe'
    recipe_name = package_section.get('name', '').strip()
    is_staged_recipes = recipe_dirname != 'recipe'

    # 1: Check that the recipe does not exist in conda-forge
    if is_staged_recipes:
        cf = gh.get_user(os.getenv('GH_ORG', 'conda-forge'))
        try:
            cf.get_repo('{}-feedstock'.format(recipe_name))
            feedstock_exists = True
        except github.UnknownObjectException as e:
            feedstock_exists = False

        if feedstock_exists:
            lints.append('Feedstock with the same name exists in conda-forge')

    # 2: Check that the recipe maintainers exists:
    maintainers = extra_section.get('recipe-maintainers', [])
    for maintainer in maintainers:
        try:
            gh.get_user(maintainer)
        except github.UnknownObjectException as e:
            lints.append('Recipe maintainer "{}" does not exist'.format(maintainer))


def selector_lines(lines):
    # Using the same pattern defined in conda-build (metadata.py),
    # we identify selectors.
    sel_pat = re.compile(r'(.+?)\s*(#.*)?\[([^\[\]]+)\](?(2).*)$')

    for i, line in enumerate(lines):
        line = line.rstrip()
        if line.lstrip().startswith('#'):
            # Don't bother with comment only lines
            continue
        m = sel_pat.match(line)
        if m:
            m.group(3)
            yield line, i


def main(recipe_dir, conda_forge=False):
    recipe_dir = os.path.abspath(recipe_dir)
    recipe_meta = os.path.join(recipe_dir, 'meta.yaml')
    if not os.path.exists(recipe_dir):
        raise IOError('Feedstock has no recipe/meta.yaml.')

    env = jinja2.Environment(undefined=NullUndefined)

    with io.open(recipe_meta, 'rt') as fh:
        content = env.from_string(''.join(fh)).render(os=os)
        meta = ruamel.yaml.load(content, ruamel.yaml.RoundTripLoader)
    results = lintify(meta, recipe_dir, conda_forge)
    return results
