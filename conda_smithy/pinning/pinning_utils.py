import re
from cf_pinning import pinning


def get_replacements(sections, section_name, pins=pinning):
    replacements = []
    for dep in sections.get(section_name, []):
        for name, versions in pins.items():
            version = versions[section_name]
            pin = '%s %s' % (name, version)
            dep_split = dep.split(' ', 1)
            actual_name = dep_split[0]
            actual_version = '' if len(dep_split) == 1 else dep_split[1]
            if actual_version == '*':
                continue
            if re.match(r'^\s*%s\s*' % name, actual_name) and dep != pin:
                replacements.append((dep, pin))
    return replacements


def replace_strings(replacements, raw_text):
    for orig, new in replacements:
        if orig == new:
            continue
        raw_text = re.sub(
            # Use capture groups to get the indentation correct.
            # (|#.*) replaces (#.*)? to circumvent the "unmatched group" error
            # see: https://bugs.python.org/issue1519638
            r'(^\s*)%s(\s*)(|#.*)$' % re.escape(orig),
            r'\1%s\2\3' % new,
            raw_text,
            count=1,
            flags=re.MULTILINE
        )
    return raw_text


def update_recipe_pinning(parsed_recipe, raw_recipe):
    replacements = []
    for section_name in ['run', 'build']:
        requirements = parsed_recipe.get('requirements')
        if not requirements:
            continue
        for obs_pin, exp_pin in get_replacements(requirements, section_name):
            replacements.append(('- %s' % obs_pin, '- %s' % exp_pin))

    if replacements:
        current_build_number = parsed_recipe['build']['number']
        replacements.append((
            'number: {}'.format(current_build_number),
            'number: {}'.format(current_build_number + 1)
        ))

    changed_recipe = replace_strings(replacements, raw_recipe)
    has_changed = bool(replacements)
    return changed_recipe, has_changed
