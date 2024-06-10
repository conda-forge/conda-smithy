import functools
import io
import operator as op
import os
from pathlib import Path
import random
import stat
import string
import shutil
import tempfile
import unittest

import git
from git.index.typ import BlobFilter

import conda_smithy.feedstock_io as fio


def keep_dir(dirname):
    keep_filename = Path(dirname, ".keep")
    with io.open(keep_filename, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("")


def parameterize():
    for pathfunc in [
        lambda pth, tmp_dir: str(Path(pth).relative_to(tmp_dir)),
        lambda pth, tmp_dir: pth,
    ]:
        for get_repo in [
            lambda tmp_dir: None,
            lambda tmp_dir: git.Repo.init(tmp_dir),
        ]:
            try:
                tmp_dir = tempfile.mkdtemp()
                keep_dir(tmp_dir)

                old_dir = Path.cwd()
                os.chdir(tmp_dir)

                yield (
                    tmp_dir,
                    get_repo(tmp_dir),
                    lambda pth: pathfunc(pth, tmp_dir),
                )
            finally:
                os.chdir(old_dir)
                shutil.rmtree(tmp_dir)


class TestFeedstockIO(unittest.TestCase):
    def setUp(self):
        self.old_dir = Path.cwd()

        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

        with io.open(
            Path(".keep").resolve(), "w", encoding="utf-8", newline="\n"
        ) as fh:
            fh.write("")

    def test_repo(self):
        for tmp_dir, repo, pathfunc in parameterize():
            if repo is None:
                self.assertTrue(fio.get_repo(pathfunc(tmp_dir)) is None)
            else:
                self.assertIsInstance(
                    fio.get_repo(pathfunc(tmp_dir)), git.Repo
                )

                random_path = "".join(
                    x + ("/" if random.random() > 0.5 else "")
                    for x in string.ascii_lowercase
                )

                possible_repo_subdir = Path(tmp_dir, random_path)
                possible_repo_subdir.mkdir(parents=True)
                assert fio.get_repo_root(possible_repo_subdir) == tmp_dir

    def test_set_exe_file(self):
        perms = [stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH]

        set_mode = functools.reduce(op.or_, perms)

        for set_exe in [True, False]:
            for tmp_dir, repo, pathfunc in parameterize():
                filename = "test.txt"
                filepath = Path(tmp_dir, filename)
                with io.open(
                    filepath, "w", encoding="utf-8", newline="\n"
                ) as fh:
                    fh.write("")
                if repo is not None:
                    repo.index.add([str(filepath)])

                fio.set_exe_file(pathfunc(str(filepath)), set_exe)

                file_mode = filepath.stat().st_mode
                self.assertEqual(file_mode & set_mode, int(set_exe) * set_mode)
                if repo is not None:
                    blob = next(
                        repo.index.iter_blobs(BlobFilter(str(filepath)))
                    )[1]
                    self.assertEqual(
                        blob.mode & set_mode, int(set_exe) * set_mode
                    )

    def test_write_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for filename in ["test.txt", "dir1/dir2/test.txt"]:
                filename = Path(tmp_dir, filename)

                write_text = "text"

                with fio.write_file(pathfunc(str(filename))) as fh:
                    fh.write(write_text)
                if repo is not None:
                    repo.index.add([str(filename)])

                read_text = ""
                with io.open(filename, "r", encoding="utf-8") as fh:
                    read_text = fh.read()

                self.assertEqual(write_text, read_text)

                if repo is not None:
                    blob = next(
                        repo.index.iter_blobs(BlobFilter(str(filename)))
                    )[1]
                    read_text = blob.data_stream[3].read().decode("utf-8")

                    self.assertEqual(write_text, read_text)

    def test_touch_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for filename in ["test.txt", "dir1/dir2/test.txt"]:
                filename = Path(tmp_dir, filename)

                fio.touch_file(pathfunc(filename))

                read_text = ""
                with io.open(filename, "r", encoding="utf-8") as fh:
                    read_text = fh.read()

                self.assertEqual("", read_text)

                if repo is not None:
                    blob = next(
                        repo.index.iter_blobs(BlobFilter(str(filename)))
                    )[1]
                    read_text = blob.data_stream[3].read().decode("utf-8")

                    self.assertEqual("", read_text)

    def test_remove_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for filename in ["test.txt", "dir1/dir2/test.txt"]:
                dirname = Path(filename).parent
                Path(dirname).mkdir(parents=True, exist_ok=True)

                filename = str(Path(tmp_dir, filename))

                with io.open(
                    filename, "w", encoding="utf-8", newline="\n"
                ) as fh:
                    fh.write("")
                if repo is not None:
                    repo.index.add([filename])

                self.assertTrue(Path(filename).exists())
                if dirname != Path("."):
                    self.assertTrue(dirname.exists())
                    self.assertTrue(dirname.parent.exists())
                if repo is not None:
                    self.assertTrue(
                        list(repo.index.iter_blobs(BlobFilter(filename)))
                    )

                fio.remove_file(pathfunc(filename))

                self.assertFalse(Path(filename).exists())
                if dirname != Path("."):
                    self.assertFalse(dirname.exists())
                    self.assertFalse(dirname.parent.exists())
                if repo is not None:
                    self.assertFalse(
                        list(repo.index.iter_blobs(BlobFilter(filename)))
                    )

    def test_copy_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            filename1 = "test1.txt"
            filename2 = "test2.txt"

            filename1 = Path(tmp_dir, filename1)
            filename2 = Path(tmp_dir, filename2)

            write_text = "text"
            with io.open(filename1, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(write_text)

            self.assertTrue(filename1.exists())
            self.assertFalse(filename2.exists())
            if repo is not None:
                self.assertFalse(
                    list(repo.index.iter_blobs(BlobFilter(str(filename2))))
                )

            fio.copy_file(pathfunc(filename1), pathfunc(filename2))

            self.assertTrue(filename1.exists())
            self.assertTrue(filename2.exists())
            if repo is not None:
                self.assertTrue(
                    list(repo.index.iter_blobs(BlobFilter(str(filename2))))
                )

            read_text = ""
            with io.open(filename2, "r", encoding="utf-8") as fh:
                read_text = fh.read()

            self.assertEqual(write_text, read_text)

            if repo is not None:
                blob = next(repo.index.iter_blobs(BlobFilter(str(filename2))))[
                    1
                ]
                read_text = blob.data_stream[3].read().decode("utf-8")

                self.assertEqual(write_text, read_text)

    def tearDown(self):
        os.chdir(self.old_dir)
        del self.old_dir

        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir


if __name__ == "__main__":
    unittest.main()
