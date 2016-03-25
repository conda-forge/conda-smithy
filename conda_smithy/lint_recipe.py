import os

import difflib
import jinja2
import ruamel.yaml


EXPECTED_SECTION_ORDER = ['package', 'source', 'build', 'requirements', 'test', 'app', 'about', 'extra']

rootpath = os.path.abspath(os.path.dirname(__file__))

def _parse_osi():
    """
    Source: https://opensource.org/licenses/alphabetical

    """
    licenses = os.path.join(rootpath, 'osi_licenses.txt')
    with open(licenses, 'r') as f:
        lines = f.readlines()
    strings = []
    for line in lines:
        string = line[line.find("(")+1:line.find(")")]
        strings.append(string)
    return strings

class NullUndefined(jinja2.Undefined):
    def __unicode__(self):
        return unicode(self._undefined_name)


def lintify(meta, recipe_dir=None):
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
        test_files = ['run_test.py', 'run_test.sh', 'run_test.bat', 'run_test.pl']
        a_test_file_exists = (recipe_dir is not None and
                              any(os.path.exists(os.path.join(recipe_dir, test_file))
                                  for test_file in test_files))
        if not a_test_file_exists:
            lints.append('The recipe must have some tests.')

    # 5: Must have a valid OSI license.
    license = meta.get('about', {}).get('license', '')
    known = _parse_osi()
    if license not in known:
        suggestions = ' '.join(list(difflib.get_close_matches(license, known)))
        if suggestions:
            msg = '\nInstead of {} did you mean any of these: {}?'.format
            msg = msg(license, suggestions)
            lints.append(msg)
        lints.append('The recipe have a valid OSI license.')

    return lints

def main(recipe_dir):
    recipe_dir = os.path.abspath(recipe_dir)
    recipe_meta = os.path.join(recipe_dir, 'meta.yaml')
    if not os.path.exists(recipe_dir):
        raise IOError('Feedstock has no recipe/meta.yaml.')

    env = jinja2.Environment(undefined=NullUndefined)

    with open(recipe_meta, 'r') as fh:
        content = env.from_string(''.join(fh)).render()
        meta = ruamel.yaml.load(content, ruamel.yaml.RoundTripLoader)
    results = lintify(meta)
    return results
