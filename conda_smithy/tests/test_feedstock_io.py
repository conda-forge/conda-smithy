import functools
import operator as op
import os
import stat
import shutil
import tempfile
import unittest

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


    def tearDown(self):
        os.chdir(self.old_dir)
        del self.old_dir

        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir


if __name__ == '__main__':
    unittest.main()
