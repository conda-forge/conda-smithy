from contextlib import contextmanager
import os
import shutil
import tempfile
import unittest

import conda_build.metadata
import conda.api

import conda_smithy.configure_feedstock as cnfgr_fdstk
from conda_build_all.resolved_distribution import ResolvedDistribution


@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp('_recipe')
    yield tmp_dir
    shutil.rmtree(tmp_dir)


class Test_fudge_subdir(unittest.TestCase):
    def test_metadata_reading(self):
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                fh.write("""
                        package:
                           name: foo_win  # [win]
                           name: foo_osx  # [osx]
                           name: foo_the_rest  # [not (win or osx)]
                         """)
            meta = conda_build.metadata.MetaData(recipe_dir)
            config = cnfgr_fdstk.meta_config(meta)

            kwargs = {}
            if hasattr(conda_build, 'api'):
                kwargs['config'] = config

            with cnfgr_fdstk.fudge_subdir('win-64', config):
                meta.parse_again(**kwargs)
                self.assertEqual(meta.name(), 'foo_win')

            with cnfgr_fdstk.fudge_subdir('osx-64', config):
                meta.parse_again(**kwargs)
                self.assertEqual(meta.name(), 'foo_osx')

    def test_fetch_index(self):
        if hasattr(conda_build, 'api'):
            config = conda_build.api.Config()
        else:
            config = conda_build.config

        # Get the index for OSX and Windows. They should be different.
        with cnfgr_fdstk.fudge_subdir('win-64', config):
            win_index = conda.api.get_index(channel_urls=['defaults'],
                                            platform='win-64')
        with cnfgr_fdstk.fudge_subdir('osx-64', config):
            osx_index = conda.api.get_index(channel_urls=['defaults'],
                                            platform='osx-64')
        self.assertNotEqual(win_index.keys(), osx_index.keys(),
                            ('The keys for the Windows and OSX index were the same.'
                             ' Subdir is not working and will result in mis-rendering '
                             '(e.g. https://github.com/SciTools/conda-build-all/issues/49).'))

    def test_r(self):
        with tmp_directory() as recipe_dir:
            with open(os.path.join(recipe_dir, 'meta.yaml'), 'w') as fh:
                fh.write("""
                        package:
                           name: r-test
                           version: 1.0.0
                        build:
                           skip: True  # [win]
                        requirements:
                           build:
                              - r-base
                           run:
                              - r-base
                         """)
            meta = conda_build.metadata.MetaData(recipe_dir)
            config = cnfgr_fdstk.meta_config(meta)

            kwargs = {}
            if hasattr(conda_build, 'api'):
                kwargs['config'] = config

            def test(expect_skip=False):
                meta.parse_again(**kwargs)
                matrix = cnfgr_fdstk.compute_build_matrix(
                    meta
                )

                if expect_skip:
                    self.assertEqual(meta.skip(), True)

                cases_not_skipped = []
                for case in matrix:
                    pkgs, vars = cnfgr_fdstk.split_case(case)
                    with cnfgr_fdstk.enable_vars(vars):
                        if not ResolvedDistribution(meta, pkgs).skip():
                            cases_not_skipped.append(vars + sorted(pkgs))

                if expect_skip:
                    self.assertEqual(cases_not_skipped, [])

            with cnfgr_fdstk.fudge_subdir('linux-32', config):
                test()

            with cnfgr_fdstk.fudge_subdir('linux-64', config):
                test()

            with cnfgr_fdstk.fudge_subdir('win-32', config):
                test(expect_skip=True)

            with cnfgr_fdstk.fudge_subdir('win-64', config):
                test(expect_skip=True)

            with cnfgr_fdstk.fudge_subdir('osx-64', config):
                test()


if __name__ == '__main__':
    unittest.main()
