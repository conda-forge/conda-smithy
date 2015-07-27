#!/usr/bin/env python
import os.path

from setuptools import setup


tl_package = 'conda_smithy'
vn_context, vn_fname = {}, os.path.join(tl_package, '_version.py')
try:
    with open(vn_fname, 'r') as fh:
        exec(fh.read(), vn_context)
    version = vn_context.get('__version__', 'dev')
except IOError:
    version = 'dev'


def main():
    skw = dict(
        name='conda-smithy',
        version=version,
        description='A package to create repositories for conda recipes, and automate '
                    'their building with CI tools on Linux, OSX and Windows.',
        author='Phil Elson',
        author_email='pelson.pub@gmail.com',
        url='https://github.com/conda-forge/conda-smithy',
        entry_points=dict(console_scripts=[
            'conda-smithy = conda_smithy.conda_smithy:main']),
        packages=['conda_smithy',
                  'conda_smithy.feedstock_content',
                  'conda_smithy.feedstock_content.ci_support',
                  'conda_smithy.templates',
                  ],
        package_dir={'conda_smithy': 'conda_smithy',
                     'conda_smithy.feedstock_content': 'conda_smithy/feedstock_content',
                     'conda_smithy.feedstock_content.ci_support':
                        'conda_smithy/feedstock_content/ci_support',
                     'conda_smithy.templates': 'conda_smithy/templates',
                     },
        package_data={'conda_smithy.feedstock_content': ['README', '*.*'],
                      'conda_smithy.feedstock_content.ci_support': ['*'],
                      'conda_smithy.templates': ['*'],
                      },
        zip_safe=False,
        )
    setup(**skw)


if __name__ == '__main__':
    main()
