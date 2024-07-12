import functools
import io
import operator as op
import os
import random
import stat
import string
import shutil
import tempfile

import git
from git.index.typ import BlobFilter

import conda_smithy.feedstock_io as fio


def keep_dir(dirname):
    keep_filename = os.path.join(dirname, ".keep")
    with io.open(keep_filename, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("")


def parameterize():
    for pathfunc in [
        lambda pth, tmp_dir: os.path.relpath(pth, tmp_dir),
        lambda pth, tmp_dir: pth,
    ]:
        for get_repo in [
            lambda tmp_dir: None,
            lambda tmp_dir: git.Repo.init(tmp_dir),
        ]:
            try:
                tmp_dir = tempfile.mkdtemp()
                keep_dir(tmp_dir)

                old_dir = os.getcwd()
                os.chdir(tmp_dir)

                yield (
                    tmp_dir,
                    get_repo(tmp_dir),
                    lambda pth: pathfunc(pth, tmp_dir),
                )
            finally:
                os.chdir(old_dir)
                shutil.rmtree(tmp_dir)


class TestFeedstockIO:
    def setUp(self):
        self.old_dir = os.getcwd()

        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

        with io.open(
            os.path.abspath(".keep"), "w", encoding="utf-8", newline="\n"
        ) as fh:
            fh.write("")

    def test_repo(self):
        for tmp_dir, repo, pathfunc in parameterize():
            if repo is None:
                assert fio.get_repo(pathfunc(tmp_dir)) is None
            else:
                assert isinstance(fio.get_repo(pathfunc(tmp_dir)), git.Repo)
                possible_repo_subdir = os.path.join(
                    tmp_dir,
                    "".join(
                        "%s%s"
                        % (x, os.path.sep if random.random() > 0.5 else "")
                        for x in string.ascii_lowercase
                    ),
                )
                os.makedirs(possible_repo_subdir)
                assert fio.get_repo_root(possible_repo_subdir) == tmp_dir

    def test_set_exe_file(self):
        perms = [stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH]

        set_mode = functools.reduce(op.or_, perms)

        for set_exe in [True, False]:
            for tmp_dir, repo, pathfunc in parameterize():
                filename = "test.txt"
                filename = os.path.join(tmp_dir, filename)
                with io.open(
                    filename, "w", encoding="utf-8", newline="\n"
                ) as fh:
                    fh.write("")
                if repo is not None:
                    repo.index.add([filename])

                fio.set_exe_file(pathfunc(filename), set_exe)

                file_mode = os.stat(filename).st_mode
                assert file_mode & set_mode == int(set_exe) * set_mode
                if repo is not None:
                    blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
                    assert blob.mode & set_mode == int(set_exe) * set_mode

    def test_write_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for filename in ["test.txt", "dir1/dir2/test.txt"]:
                filename = os.path.join(tmp_dir, filename)

                write_text = "text"

                with fio.write_file(pathfunc(filename)) as fh:
                    fh.write(write_text)
                if repo is not None:
                    repo.index.add([filename])

                read_text = ""
                with io.open(filename, "r", encoding="utf-8") as fh:
                    read_text = fh.read()

                assert write_text == read_text

                if repo is not None:
                    blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
                    read_text = blob.data_stream[3].read().decode("utf-8")

                    assert write_text == read_text

    def test_touch_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for filename in ["test.txt", "dir1/dir2/test.txt"]:
                filename = os.path.join(tmp_dir, filename)

                fio.touch_file(pathfunc(filename))

                read_text = ""
                with io.open(filename, "r", encoding="utf-8") as fh:
                    read_text = fh.read()

                assert "" == read_text

                if repo is not None:
                    blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
                    read_text = blob.data_stream[3].read().decode("utf-8")

                    assert "" == read_text

    def test_remove_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for filename in ["test.txt", "dir1/dir2/test.txt"]:
                dirname = os.path.dirname(filename)
                if dirname and not os.path.exists(dirname):
                    os.makedirs(dirname)

                filename = os.path.join(tmp_dir, filename)

                with io.open(
                    filename, "w", encoding="utf-8", newline="\n"
                ) as fh:
                    fh.write("")
                if repo is not None:
                    repo.index.add([filename])

                assert os.path.exists(filename)
                if dirname:
                    assert os.path.exists(dirname)
                    assert os.path.exists(os.path.dirname(dirname))
                if repo is not None:
                    assert list(repo.index.iter_blobs(BlobFilter(filename)))

                fio.remove_file(pathfunc(filename))

                assert not os.path.exists(filename)
                if dirname:
                    assert not os.path.exists(dirname)
                    assert not os.path.exists(os.path.dirname(dirname))
                if repo is not None:
                    assert not list(
                        repo.index.iter_blobs(BlobFilter(filename))
                    )

    def test_copy_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            filename1 = "test1.txt"
            filename2 = "test2.txt"

            filename1 = os.path.join(tmp_dir, filename1)
            filename2 = os.path.join(tmp_dir, filename2)

            write_text = "text"
            with io.open(filename1, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(write_text)

            assert os.path.exists(filename1)
            assert not os.path.exists(filename2)
            if repo is not None:
                assert not list(repo.index.iter_blobs(BlobFilter(filename2)))

            fio.copy_file(pathfunc(filename1), pathfunc(filename2))

            assert os.path.exists(filename1)
            assert os.path.exists(filename2)
            if repo is not None:
                assert list(repo.index.iter_blobs(BlobFilter(filename2)))

            read_text = ""
            with io.open(filename2, "r", encoding="utf-8") as fh:
                read_text = fh.read()

            assert write_text == read_text

            if repo is not None:
                blob = next(repo.index.iter_blobs(BlobFilter(filename2)))[1]
                read_text = blob.data_stream[3].read().decode("utf-8")

                assert write_text == read_text

    def tearDown(self):
        os.chdir(self.old_dir)
        del self.old_dir

        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir
