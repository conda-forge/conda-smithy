import functools
import operator as op
import os
import random
import shutil
import stat
import string
import tempfile

import pygit2
import pytest

import conda_smithy.feedstock_io as fio


def keep_dir(dirname):
    keep_filename = os.path.join(dirname, ".keep")
    with open(keep_filename, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("")


def parameterize():
    for pathfunc in [
        lambda pth, tmp_dir: os.path.relpath(pth, tmp_dir),
        lambda pth, tmp_dir: pth,
    ]:
        for get_repo in [
            lambda tmp_dir: None,
            lambda tmp_dir: pygit2.init_repository(tmp_dir),
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


def test_repo() -> None:
    for tmp_dir, repo, pathfunc in parameterize():
        if repo is None:
            assert fio.get_repo(pathfunc(tmp_dir)) is None
        else:
            assert isinstance(fio.get_repo(pathfunc(tmp_dir)), pygit2.Repository)
            possible_repo_subdir = os.path.join(
                tmp_dir,
                "".join(
                    "{}{}".format(x, os.path.sep if random.random() > 0.5 else "")
                    for x in string.ascii_lowercase
                ),
            )
            os.makedirs(possible_repo_subdir)
            assert fio.get_repo_root(possible_repo_subdir) == os.path.realpath(tmp_dir)


def test_set_exe_file() -> None:
    perms = [stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH]

    set_mode = functools.reduce(op.or_, perms)

    for set_exe in [True, False]:
        for tmp_dir, repo, pathfunc in parameterize():
            basename = "test.txt"
            filename = os.path.join(tmp_dir, basename)
            with open(filename, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("")
            if repo is not None:
                repo.index.add(basename)
                repo.index.write()

            fio.set_exe_file(pathfunc(filename), set_exe)

            file_mode = os.stat(filename).st_mode
            assert file_mode & set_mode == int(set_exe) * set_mode
            if repo is not None:
                repo.index.read()
                blob = repo.index[basename]
                assert blob.mode & set_mode == int(set_exe) * set_mode


def test_write_file() -> None:
    for tmp_dir, repo, pathfunc in parameterize():
        for basename in ["test.txt", "dir1/dir2/test.txt"]:
            filename = os.path.join(tmp_dir, basename)

            write_text = "text"

            with fio.write_file(pathfunc(filename)) as fh:
                fh.write(write_text)

            read_text = ""
            with open(filename, encoding="utf-8") as fh:
                read_text = fh.read()

            assert write_text == read_text

            if repo is not None:
                repo.index.read()
                blob = repo.index[basename]
                read_text = repo[blob.id].data.decode("utf-8")

                assert write_text == read_text


def test_touch_file() -> None:
    for tmp_dir, repo, pathfunc in parameterize():
        for basename in ["test.txt", "dir1/dir2/test.txt"]:
            filename = os.path.join(tmp_dir, basename)

            fio.touch_file(pathfunc(filename))

            read_text = ""
            with open(filename, encoding="utf-8") as fh:
                read_text = fh.read()

            assert "" == read_text

            if repo is not None:
                repo.index.read()
                blob = repo.index[basename]
                read_bytes = repo[blob.id].data

                assert b"" == read_bytes


def test_remove_file() -> None:
    for tmp_dir, repo, pathfunc in parameterize():
        for basename in ["test.txt", "dir1/dir2/test.txt"]:
            dirname = os.path.dirname(basename)
            if dirname and not os.path.exists(dirname):
                os.makedirs(dirname)

            filename = os.path.join(tmp_dir, basename)

            with open(filename, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("")
            if repo is not None:
                repo.index.add(basename)
                repo.index.write()

            assert os.path.exists(filename)
            if dirname:
                assert os.path.exists(dirname)
                assert os.path.exists(os.path.dirname(dirname))
            if repo is not None:
                assert repo.index[basename] is not None

            fio.remove_file(pathfunc(filename))

            assert not os.path.exists(filename)
            if dirname:
                assert not os.path.exists(dirname)
                assert not os.path.exists(os.path.dirname(dirname))
            if repo is not None:
                repo.index.read()
                with pytest.raises(KeyError):
                    repo.index[basename]


def test_remove_dir() -> None:
    for tmp_dir, repo, pathfunc in parameterize():
        dirname = os.path.join(tmp_dir, "dir")
        os.makedirs(f"{dirname}/a")
        os.makedirs(f"{dirname}/b")
        for basename in ["dir/a/foo.txt", "dir/b/bar.txt", "dir/baz.txt"]:
            filename = os.path.join(tmp_dir, basename)

            with open(filename, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("")
            if repo is not None:
                repo.index.add(basename)
                repo.index.write()

            assert os.path.exists(filename)
            if repo is not None:
                assert repo.index[basename] is not None

        fio.remove_file_or_dir(pathfunc(dirname))

        for basename in ["dir/a/foo.txt", "dir/b/bar.txt", "dir/baz.txt"]:
            assert not os.path.exists(filename)
            if repo is not None:
                repo.index.read()
                with pytest.raises(KeyError):
                    repo.index[basename]
        assert not os.path.exists(dirname)


def test_copy_file() -> None:
    for tmp_dir, repo, pathfunc in parameterize():
        basename1 = "test1.txt"
        basename2 = "test2.txt"

        filename1 = os.path.join(tmp_dir, basename1)
        filename2 = os.path.join(tmp_dir, basename2)

        write_text = "text"
        with open(filename1, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(write_text)

        assert os.path.exists(filename1)
        assert not os.path.exists(filename2)
        if repo is not None:
            with pytest.raises(KeyError):
                repo.index[basename2]

        fio.copy_file(pathfunc(filename1), pathfunc(filename2))

        assert os.path.exists(filename1)
        assert os.path.exists(filename2)
        if repo is not None:
            repo.index.read()
            assert repo.index[basename2] is not None

        read_text = ""
        with open(filename2, encoding="utf-8") as fh:
            read_text = fh.read()

        assert write_text == read_text

        if repo is not None:
            blob = repo.index[basename2]
            read_text = repo[blob.id].data.decode("utf-8")

            assert write_text == read_text
