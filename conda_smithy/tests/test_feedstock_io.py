from __future__ import unicode_literals

import functools
import io
import operator as op
import os
import stat
import shutil
import tempfile
import unittest

import git
from git.index.typ import BlobFilter

import conda_smithy.feedstock_io as fio


def keep_dir(dirname):
    keep_filename = os.path.join(dirname, ".keep")
    with io.open(keep_filename, "w", encoding="utf-8") as fh:
        fh.write("")


def parameterize():
    for pathfunc in [
        lambda pth, tmp_dir: os.path.relpath(pth, tmp_dir),
        lambda pth, tmp_dir: pth
    ]:
        for get_repo in [
            lambda tmp_dir: None,
            lambda tmp_dir: git.Repo.init(tmp_dir)
        ]:
            try:
                tmp_dir = tempfile.mkdtemp()
                keep_dir(tmp_dir)

                old_dir = os.getcwd()
                os.chdir(tmp_dir)

                yield (
                    tmp_dir,
                    get_repo(tmp_dir),
                    lambda pth: pathfunc(pth, tmp_dir)
                )
            finally:
                os.chdir(old_dir)
                shutil.rmtree(tmp_dir)


class TestFeedstockIO(unittest.TestCase):
    def setUp(self):
        self.old_dir = os.getcwd()

        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

        with io.open(os.path.abspath(".keep"), "w", encoding="utf-8") as fh:
            fh.write("")


    def test_repo(self):
        for tmp_dir, repo, pathfunc in parameterize():
            if repo is None:
                self.assertTrue(
                    fio.get_repo(pathfunc(tmp_dir)) is None
                )
            else:
                self.assertIsInstance(
                    fio.get_repo(pathfunc(tmp_dir)),
                    git.Repo
                )


    def test_get_file_blob(self):
        for tmp_dir, repo, pathfunc in parameterize():
            if repo is None:
                continue

            filename = "test.txt"
            filename = os.path.join(tmp_dir, filename)

            with io.open(filename, "w", encoding="utf-8") as fh:
                fh.write("")

            repo.index.add([filename])

            blob = None
            try:
                blob = fio.get_file_blob(repo, filename)
            except StopIteration:
                self.fail("Unable to find the file we added.")

            self.assertEqual(blob.name, os.path.basename(filename))


    def test_get_mode_file(self):
        perms = [
            stat.S_IWUSR,
            stat.S_IXUSR,
            stat.S_IRUSR,
            stat.S_IXGRP,
            stat.S_IRGRP,
            stat.S_IROTH
        ]

        set_mode = functools.reduce(op.or_, perms)

        for tmp_dir, repo, pathfunc in parameterize():
            filename = "test.txt"
            filename = os.path.join(tmp_dir, filename)
            with io.open(filename, "w", encoding="utf-8") as fh:
                fh.write("")

            os.chmod(filename, set_mode)
            if repo is not None:
                blob = repo.index.add([filename])[0].to_blob(repo)
                blob.mode = set_mode
                repo.index.add([blob])

            file_mode = fio.get_mode_file(pathfunc(filename))
            self.assertEqual(file_mode & set_mode, set_mode)


    def test_set_mode_file(self):
        perms = [
            stat.S_IWUSR,
            stat.S_IXUSR,
            stat.S_IRUSR,
            stat.S_IXGRP,
            stat.S_IRGRP,
            stat.S_IROTH
        ]

        set_mode = functools.reduce(op.or_, perms)

        for tmp_dir, repo, pathfunc in parameterize():
            filename = "test.txt"
            filename = os.path.join(tmp_dir, filename)
            with io.open(filename, "w", encoding="utf-8") as fh:
                fh.write("")
            if repo is not None:
                repo.index.add([filename])

            fio.set_mode_file(pathfunc(filename), set_mode)

            file_mode = os.stat(filename).st_mode
            self.assertEqual(file_mode & set_mode, set_mode)
            if repo is not None:
                blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
                self.assertEqual(blob.mode & set_mode, set_mode)


    def test_set_exe_file(self):
        perms = [
            stat.S_IXUSR,
            stat.S_IXGRP,
            stat.S_IXOTH
        ]

        set_mode = functools.reduce(op.or_, perms)

        for set_exe in [True, False]:
            for tmp_dir, repo, pathfunc in parameterize():
                filename = "test.txt"
                filename = os.path.join(tmp_dir, filename)
                with io.open(filename, "w", encoding="utf-8") as fh:
                    fh.write("")
                if repo is not None:
                    repo.index.add([filename])

                fio.set_exe_file(pathfunc(filename), set_exe)

                file_mode = os.stat(filename).st_mode
                self.assertEqual(file_mode & set_mode,
                                 int(set_exe) * set_mode)
                if repo is not None:
                    blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
                    self.assertEqual(blob.mode & set_mode,
                                     int(set_exe) * set_mode)


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

                self.assertEqual(write_text, read_text)

                if repo is not None:
                    blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
                    read_text = blob.data_stream[3].read().decode("utf-8")

                    self.assertEqual(write_text, read_text)


    def test_touch_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for filename in ["test.txt", "dir1/dir2/test.txt"]:
                filename = os.path.join(tmp_dir, filename)

                fio.touch_file(pathfunc(filename))

                read_text = ""
                with io.open(filename, "r", encoding="utf-8") as fh:
                    read_text = fh.read()

                self.assertEqual("", read_text)

                if repo is not None:
                    blob = next(repo.index.iter_blobs(BlobFilter(filename)))[1]
                    read_text = blob.data_stream[3].read().decode("utf-8")

                    self.assertEqual("", read_text)


    def test_remove_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            for filename in ["test.txt", "dir1/dir2/test.txt"]:
                dirname = os.path.dirname(filename)
                if dirname and not os.path.exists(dirname):
                    os.makedirs(dirname)

                filename = os.path.join(tmp_dir, filename)

                with io.open(filename, "w", encoding="utf-8") as fh:
                    fh.write("")
                if repo is not None:
                    repo.index.add([filename])

                self.assertTrue(os.path.exists(filename))
                if dirname:
                    self.assertTrue(os.path.exists(dirname))
                    self.assertTrue(os.path.exists(os.path.dirname(dirname)))
                if repo is not None:
                    self.assertTrue(
                        list(repo.index.iter_blobs(BlobFilter(filename)))
                    )

                fio.remove_file(pathfunc(filename))

                self.assertFalse(os.path.exists(filename))
                if dirname:
                    self.assertFalse(os.path.exists(dirname))
                    self.assertFalse(os.path.exists(os.path.dirname(dirname)))
                if repo is not None:
                    self.assertFalse(
                        list(repo.index.iter_blobs(BlobFilter(filename)))
                    )


    def test_copy_file(self):
        for tmp_dir, repo, pathfunc in parameterize():
            filename1 = "test1.txt"
            filename2 = "test2.txt"

            filename1 = os.path.join(tmp_dir, filename1)
            filename2 = os.path.join(tmp_dir, filename2)

            write_text = "text"
            with io.open(filename1, "w", encoding="utf-8") as fh:
                fh.write(write_text)

            self.assertTrue(os.path.exists(filename1))
            self.assertFalse(os.path.exists(filename2))
            if repo is not None:
                self.assertFalse(
                    list(repo.index.iter_blobs(BlobFilter(filename2)))
                )

            fio.copy_file(pathfunc(filename1), pathfunc(filename2))

            self.assertTrue(os.path.exists(filename1))
            self.assertTrue(os.path.exists(filename2))
            if repo is not None:
                self.assertTrue(
                    list(repo.index.iter_blobs(BlobFilter(filename2)))
                )

            read_text = ""
            with io.open(filename2, "r", encoding="utf-8") as fh:
                read_text = fh.read()

            self.assertEqual(write_text, read_text)

            if repo is not None:
                blob = next(repo.index.iter_blobs(BlobFilter(filename2)))[1]
                read_text = blob.data_stream[3].read().decode("utf-8")

                self.assertEqual(write_text, read_text)


    def tearDown(self):
        os.chdir(self.old_dir)
        del self.old_dir

        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir


if __name__ == '__main__':
    unittest.main()
