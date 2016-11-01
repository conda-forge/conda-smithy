import functools
import operator as op
import os
import stat
import shutil
import tempfile
import unittest

import git

import conda_smithy.feedstock_io as fio


class TestFeedstockIO_wo_Git(unittest.TestCase):
    def setUp(self):
        self.old_dir = os.getcwd()

        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)


    def test_repo(self):
        self.assertTrue(fio.get_repo("") is None)


    def test_get_mode_file(self):
        filename = "test.txt"

        with open(filename, "w") as fh:
            fh.write("")

        perms = [
            stat.S_IWUSR,
            stat.S_IXUSR,
            stat.S_IRUSR,
            stat.S_IXGRP,
            stat.S_IRGRP,
            stat.S_IROTH
        ]

        set_mode = functools.reduce(op.or_, perms)

        os.chmod(filename, set_mode)

        file_mode = fio.get_mode_file(filename)

        self.assertEqual(file_mode & set_mode, set_mode)


    def test_set_mode_file(self):
        filename = "test.txt"

        with open(filename, "w") as fh:
            fh.write("")

        perms = [
            stat.S_IWUSR,
            stat.S_IXUSR,
            stat.S_IRUSR,
            stat.S_IXGRP,
            stat.S_IRGRP,
            stat.S_IROTH
        ]

        set_mode = functools.reduce(op.or_, perms)

        fio.set_mode_file(filename, set_mode)

        file_mode = os.stat(filename).st_mode

        self.assertEqual(file_mode & set_mode, set_mode)


    def test_write_file(self):
        filename = "test.txt"

        write_text = "text"
        with fio.write_file(filename) as fh:
            fh.write(write_text)

        read_text = ""
        with open(filename, "r") as fh:
            read_text = fh.read()

        self.assertEqual(write_text, read_text)


    def test_touch_file(self):
        filename = "test.txt"

        fio.touch_file(filename)

        read_text = ""
        with open(filename, "r") as fh:
            read_text = fh.read()

        self.assertEqual("", read_text)


    def test_remove_file(self):
        filename = "test.txt"

        with open(filename, "w") as fh:
            fh.write("")

        self.assertTrue(os.path.exists(filename))

        fio.remove_file(filename)

        self.assertFalse(os.path.exists(filename))


    def test_copy_file(self):
        filename1 = "test1.txt"
        filename2 = "test2.txt"

        write_text = "text"
        with open(filename1, "w") as fh:
            fh.write(write_text)

        self.assertTrue(os.path.exists(filename1))
        self.assertFalse(os.path.exists(filename2))

        fio.copy_file(filename1, filename2)

        self.assertTrue(os.path.exists(filename1))
        self.assertTrue(os.path.exists(filename2))

        read_text = ""
        with open(filename2, "r") as fh:
            read_text = fh.read()

        self.assertEqual(write_text, read_text)


    def tearDown(self):
        os.chdir(self.old_dir)
        del self.old_dir

        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir


class TestFeedstockIO_w_Git(unittest.TestCase):
    def setUp(self):
        self.old_dir = os.getcwd()

        self.tmp_dir = tempfile.mkdtemp()
        self.repo = git.Repo.init(self.tmp_dir)
        os.chdir(self.tmp_dir)


    def test_repo(self):
        self.assertTrue(isinstance(fio.get_repo(""), git.Repo))


    def test_get_mode_file(self):
        filename = "test.txt"

        with open(filename, "w") as fh:
            fh.write("")

        perms = [
            stat.S_IWUSR,
            stat.S_IXUSR,
            stat.S_IRUSR,
            stat.S_IXGRP,
            stat.S_IRGRP,
            stat.S_IROTH
        ]

        set_mode = functools.reduce(op.or_, perms)

        blob = self.repo.index.add([filename])[0].to_blob(self.repo)
        blob.mode = set_mode
        self.repo.index.add([blob])

        os.chmod(filename, set_mode)

        file_mode = fio.get_mode_file(filename)

        self.assertEqual(file_mode & set_mode, set_mode)


    def test_set_mode_file(self):
        filename = "test.txt"

        with open(filename, "w") as fh:
            fh.write("")

        self.repo.index.add([filename])

        perms = [
            stat.S_IWUSR,
            stat.S_IXUSR,
            stat.S_IRUSR,
            stat.S_IXGRP,
            stat.S_IRGRP,
            stat.S_IROTH
        ]

        set_mode = functools.reduce(op.or_, perms)

        fio.set_mode_file(filename, set_mode)

        file_mode = os.stat(filename).st_mode

        self.assertEqual(file_mode & set_mode, set_mode)


    def test_write_file(self):
        filename = "test.txt"

        write_text = "text"
        with fio.write_file(filename) as fh:
            fh.write(write_text)

        read_text = ""
        with open(filename, "r") as fh:
            read_text = fh.read()

        self.assertEqual(write_text, read_text)

        filter_filename = lambda _: _[1].path == filename
        blob = list(self.repo.index.iter_blobs(filter_filename))[0][1]
        read_text = blob.data_stream[3].read().decode("utf-8")

        self.assertEqual(write_text, read_text)


    def tearDown(self):
        os.chdir(self.old_dir)
        del self.old_dir

        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir


if __name__ == '__main__':
    unittest.main()
