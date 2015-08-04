#!/usr/bin/env python
import os.path

from setuptools import setup, find_packages


tl_package = 'conda_smithy'
vn_context, vn_fname = {}, os.path.join(tl_package, '_version.py')
try:
    with open(vn_fname, 'r') as fh:
        exec(fh.read(), vn_context)
    version = vn_context.get('__version__', 'dev')
except IOError:
    version = 'dev'


with open('requirements.txt') as f:
    requirements = f.read().splitlines()


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
        packages=find_packages(),
        install_requires=requirements,
        include_package_data=True,
        # As conda-smithy has resources as part of the codebase, it is
        # not zip-safe.
        zip_safe=False,
        )
    setup(**skw)


if __name__ == '__main__':
    main()
