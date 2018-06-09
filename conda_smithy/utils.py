import shutil
import tempfile
import jinja2
import six
import datetime
import time
from collections import defaultdict
from contextlib import contextmanager

@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp('_recipe')
    yield tmp_dir
    shutil.rmtree(tmp_dir)


class NullUndefined(jinja2.Undefined):
    def __unicode__(self):
        return self._undefined_name

    def __getattr__(self, name):
        return '{}.{}'.format(self, name)

    def __getitem__(self, name):
        return '{}["{}"]'.format(self, name)


class MockOS(dict):
    def __init__(self):
        self.environ = defaultdict(lambda: '')


def render_meta_yaml(text):
    env = jinja2.Environment(undefined=NullUndefined)

    # stub out cb3 jinja2 functions - they are not important for linting
    #    if we don't stub them out, the ruamel.yaml load fails to interpret them
    #    we can't just use conda-build's api.render functionality, because it would apply selectors
    env.globals.update(dict(compiler=lambda x: x + '_compiler_stub',
                            pin_subpackage=lambda *args, **kwargs: 'subpackage_stub',
                            pin_compatible=lambda *args, **kwargs: 'compatible_pin_stub',
                            cdt=lambda *args, **kwargs: 'cdt_stub',
                            load_file_regex=lambda *args, **kwargs: \
                                    defaultdict(lambda : ''),
                            datetime=datetime,
                            time=time,
                            ))
    
    content = env.from_string(text).render(os=MockOS())
    return content
