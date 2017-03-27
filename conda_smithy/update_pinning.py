# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import argparse
import io
import os

import jinja2
import ruamel.yaml

from conda_smithy.pinning import update_recipe_pinning
from conda_smithy.feedstock_io import write_file


class NullUndefined(jinja2.Undefined):
    def __unicode__(self):
        return self._undefined_name

    def __getattr__(self, name):
        return '{}.{}'.format(self, name)

    def __getitem__(self, name):
        return '{}["{}"]'.format(self, name)


def update_pinning(jinja_env, recipe_meta, out_meta=None):
    if out_meta is None:
        out_meta = recipe_meta

    with io.open(recipe_meta, 'rt') as fh:
        content = ''.join(fh)
        rendered_content = jinja_env.from_string(content).render(os=os)
        recipe = ruamel.yaml.load(rendered_content, ruamel.yaml.RoundTripLoader)

    changed_content, has_changed = update_recipe_pinning(recipe, content)

    if has_changed:
        with write_file(out_meta) as fh:
            fh.write(changed_content)


def main(feedstock_dir):
    feedstock_dir = os.path.abspath(feedstock_dir)
    recipe_meta = os.path.join(feedstock_dir, 'recipe', 'meta.yaml')
    if not os.path.exists(recipe_meta):
        raise IOError('Feedstock has no recipe/meta.yaml.')

    env = jinja2.Environment(undefined=NullUndefined)
    update_pinning(env, recipe_meta)

if __name__ == '__main__':
    description = 'commandline tool to update dependency pinnings in meta.yaml files'
    parser = argparse.ArgumentParser('update_pinnings', description=description)
    parser.add_argument('meta_yaml', help='path to input conda recipe')
    out_help = 'path to output conda recipe - overwriting input if unset'
    parser.add_argument('--out_file', help=out_help)
    args = parser.parse_args()

    env = jinja2.Environment(undefined=NullUndefined)
    update_pinning(env, args.meta_yaml, args.out_file)
