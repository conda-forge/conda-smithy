import conda_build.metadata
import conda.api

import conda_smithy.configure_feedstock as cnfgr_fdstk


class Test_fudge_subdir(object):
    def test_metadata_reading(self, tmpdir):
        tmpdir.join('meta.yaml').write("""
                        package:
                           name: foo_win  # [win]
                           name: foo_osx  # [osx]
                           name: foo_the_rest  # [not (win or osx)]
                         """)
        meta = conda_build.metadata.MetaData(str(tmpdir))
        config = cnfgr_fdstk.meta_config(meta)

        kwargs = {}
        if hasattr(conda_build, 'api'):
            kwargs['config'] = config

        with cnfgr_fdstk.fudge_subdir('win-64', config):
            meta.parse_again(**kwargs)
            assert meta.name() == 'foo_win'

        with cnfgr_fdstk.fudge_subdir('osx-64', config):
            meta.parse_again(**kwargs)
            assert meta.name() == 'foo_osx'

    def test_fetch_index(self):
        if hasattr(conda_build, 'api'):
            config = conda_build.api.Config()
        else:
            config = conda_build.config

        # Get the index for OSX and Windows. They should be different.
        with cnfgr_fdstk.fudge_subdir('win-64', config):
            win_index = conda.api.get_index()
        with cnfgr_fdstk.fudge_subdir('osx-64', config):
            osx_index = conda.api.get_index()
        assert win_index.keys() != osx_index.keys(), \
                            ('The keys for the Windows and OSX index were the same.'
                             ' Subdir is not working and will result in mis-rendering '
                             '(e.g. https://github.com/SciTools/conda-build-all/issues/49).')
