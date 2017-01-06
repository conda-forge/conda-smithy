from __future__ import unicode_literals

import functools
import io
import operator as op
import os
import stat
import sys

import conda_smithy.feedstock_io as fio
import git
import py
import pytest
from git.index.typ import BlobFilter


class TestFeedstockIO(object):

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        tmpdir.chdir()
        tmpdir.join('.keep').write('')

    @pytest.fixture(params=['relative', 'absolute'])
    def path(self, tmpdir_factory, tmpdir, request):
        result = tmpdir_factory.mktemp('smithy')
        if request.param == 'relative':
            result = tmpdir.bestrelpath(result)
        return str(result)

    @pytest.fixture(params=['git', 'no-vcs'])
    def repo(self, request, path):
        if request.param == 'git':
            return git.Repo.init(str(path))
        else:
            return None

    def test_repo(self, repo, path):
        if repo is None:
            assert fio.get_repo(str(path)) is None
        else:
            assert isinstance(fio.get_repo(str(path)), git.Repo)

    @pytest.mark.parametrize('set_exe', [True, False])
    def test_set_exe_file(self, set_exe, repo, path):
        if set_exe and sys.platform.startswith('win'):
            pytest.skip('Not possible to set executable flag on Windows')

        perms = [
            stat.S_IXUSR,
            stat.S_IXGRP,
            stat.S_IXOTH
        ]

        set_mode = functools.reduce(op.or_, perms)

        filename = py.path.local(path).join("test.txt")
        filename.ensure(file=1)
        if repo is not None:
            repo.index.add([str(filename)])

        fio.set_exe_file(str(filename), set_exe)

        file_mode = os.stat(str(filename)).st_mode
        assert file_mode & set_mode == \
                         int(set_exe) * set_mode
        if repo is not None:
            blob = next(repo.index.iter_blobs(BlobFilter(str(filename))))[1]
            assert blob.mode & set_mode == \
                             int(set_exe) * set_mode

    @pytest.mark.parametrize('filename', ["test.txt", "dir1/dir2/test.txt"])
    def test_write_file(self, filename, path, repo):
        filename = os.path.join(path, filename)

        write_text = "text"

        with fio.write_file(filename) as fh:
            fh.write(write_text)
        if repo is not None:
            repo.index.add([filename])

        with io.open(filename, "r", encoding="utf-8") as fh:
            read_text = fh.read()

        assert write_text == read_text

        if repo is not None:
            blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
            read_text = blob.data_stream[3].read().decode("utf-8")

        assert write_text == read_text

    @pytest.mark.parametrize('filename', ["test.txt", "dir1/dir2/test.txt"])
    def test_touch_file(self, path, filename, repo):
        filename = os.path.join(path, filename)

        fio.touch_file(filename)

        with io.open(filename, "r", encoding="utf-8") as fh:
            read_text = fh.read()

        assert "" == read_text

        if repo is not None:
            blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
            read_text = blob.data_stream[3].read().decode("utf-8")

            assert "" == read_text

    @pytest.mark.parametrize('filename', ["test.txt", "dir1/dir2/test.txt"])
    def test_remove_file(self, path, filename, repo, tmpdir):
        dirname = os.path.dirname(filename)
        filename = py.path.local(path).join(filename)
        filename.ensure(file=1)

        if repo is not None:
            repo.index.add([str(filename)])

        assert filename.isfile()
        if repo is not None:
            assert list(repo.index.iter_blobs(BlobFilter(str(filename))))

        fio.remove_file(str(filename))

        assert not filename.isfile()
        if dirname:
            assert not py.path.local(filename.dirname).isdir()
        if repo is not None:
            assert not list(repo.index.iter_blobs(BlobFilter(str(filename))))

    def test_copy_file(self, repo, path):
        filename1 = os.path.join(path, "test1.txt")
        filename2 = os.path.join(path, "test2.txt")

        write_text = 'text'
        py.path.local(filename1).write(write_text)

        assert os.path.isfile(filename1)
        assert not os.path.isfile(filename2)
        if repo is not None:
            assert not list(repo.index.iter_blobs(BlobFilter(filename2)))

        fio.copy_file(os.path.join(path, str(filename1)), os.path.join(path, str(filename2)))

        assert os.path.isfile(filename1)
        assert os.path.isfile(filename2)
        if repo is not None:
            assert list(repo.index.iter_blobs(BlobFilter(filename2)))

        with io.open(filename2, "r", encoding="utf-8") as fh:
            read_text = fh.read()

        assert write_text == read_text

        if repo is not None:
            blob = next(repo.index.iter_blobs(BlobFilter(filename2)))[1]
            read_text = blob.data_stream[3].read().decode("utf-8")

            assert write_text == read_text
