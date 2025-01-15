import functools
import operator as op
import os
import random
import shutil
import stat
import string
import tempfile
import unittest

import pygit2

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


class TestFeedstockIO(unittest.TestCase):
    def setUp(self):
        self.old_dir = os.getcwd()

        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

        with open(
            os.path.abspath(".keep"), "w", encoding="utf-8", newline="\n"
        ) as fh:
            fh.write("")

    def test_repo(self):
        for tmp_dir, repo, pathfunc in parameterize():
            if repo is None:
                self.assertTrue(fio.get_repo(pathfunc(tmp_dir)) is None)
            else:
                self.assertIsInstance(
                    fio.get_repo(pathfunc(tmp_dir)), pygit2.Repository
                )
                possible_repo_subdir = os.path.join(
                    tmp_dir,
                    "".join(
                        "{}{}".format(
                            x, os.path.sep if random.random() > 0.5 else ""
                        )
                        for x in string.ascii_lowercase
                    ),
                )
                os.makedirs(possible_repo_subdir)
                assert fio.get_repo_root(possible_repo_subdir) == os.path.realpath(tmp_dir)

    def test_set_exe_file(self):
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
                self.assertEqual(file_mode & set_mode, int(set_exe) * set_mode)
                if repo is not None:
                    repo.index.read()
                    blob = repo.index[basename]
                    self.assertEqual(
                        blob.mode & set_mode, int(set_exe) * set_mode
                    )

    def test_write_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for basename in ["test.txt", "dir1/dir2/test.txt"]:
                filename = os.path.join(tmp_dir, basename)

                write_text = "text"

                with fio.write_file(pathfunc(filename)) as fh:
                    fh.write(write_text)

                read_text = ""
                with open(filename, encoding="utf-8") as fh:
                    read_text = fh.read()

                self.assertEqual(write_text, read_text)

                if repo is not None:
                    repo.index.read()
                    blob = repo.index[basename]
                    read_text = repo[blob.id].data.decode("utf-8")

                    self.assertEqual(write_text, read_text)

    def test_touch_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for basename in ["test.txt", "dir1/dir2/test.txt"]:
                filename = os.path.join(tmp_dir, basename)

                fio.touch_file(pathfunc(filename))

                read_text = ""
                with open(filename, encoding="utf-8") as fh:
                    read_text = fh.read()

                self.assertEqual("", read_text)

                if repo is not None:
                    repo.index.read()
                    blob = repo.index[basename]
                    read_bytes = repo[blob.id].data

                    self.assertEqual(b"", read_bytes)

    def test_remove_file(self):
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

                self.assertTrue(os.path.exists(filename))
                if dirname:
                    self.assertTrue(os.path.exists(dirname))
                    self.assertTrue(os.path.exists(os.path.dirname(dirname)))
                if repo is not None:
                    self.assertIsNotNone(repo.index[basename])

                fio.remove_file(pathfunc(filename))

                self.assertFalse(os.path.exists(filename))
                if dirname:
                    self.assertFalse(os.path.exists(dirname))
                    self.assertFalse(os.path.exists(os.path.dirname(dirname)))
                if repo is not None:
                    repo.index.read()
                    self.assertRaises(KeyError, lambda: repo.index[basename])

    def test_remove_dir(self):
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

                self.assertTrue(os.path.exists(filename))
                if repo is not None:
                    self.assertIsNotNone(repo.index[basename])

            fio.remove_file_or_dir(pathfunc(dirname))

            for basename in ["dir/a/foo.txt", "dir/b/bar.txt", "dir/baz.txt"]:
                self.assertFalse(os.path.exists(filename))
                if repo is not None:
                    repo.index.read()
                    self.assertRaises(KeyError, lambda: repo.index[basename])
            self.assertFalse(os.path.exists(dirname))

    def test_copy_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            basename1 = "test1.txt"
            basename2 = "test2.txt"

            filename1 = os.path.join(tmp_dir, basename1)
            filename2 = os.path.join(tmp_dir, basename2)

            write_text = "text"
            with open(filename1, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(write_text)

            self.assertTrue(os.path.exists(filename1))
            self.assertFalse(os.path.exists(filename2))
            if repo is not None:
                self.assertRaises(KeyError, lambda: repo.index[basename2])

            fio.copy_file(pathfunc(filename1), pathfunc(filename2))

            self.assertTrue(os.path.exists(filename1))
            self.assertTrue(os.path.exists(filename2))
            if repo is not None:
                repo.index.read()
                self.assertIsNotNone(repo.index[basename2])

            read_text = ""
            with open(filename2, encoding="utf-8") as fh:
                read_text = fh.read()

            self.assertEqual(write_text, read_text)

            if repo is not None:
                blob = repo.index[basename2]
                read_text = repo[blob.id].data.decode("utf-8")

                self.assertEqual(write_text, read_text)

    def tearDown(self):
        os.chdir(self.old_dir)
        del self.old_dir

        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir


if __name__ == "__main__":
    unittest.main()
