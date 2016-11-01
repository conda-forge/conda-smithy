from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

import conda_smithy.feedstock_io as fio


class TestFeedstockIO(unittest.TestCase):
    def setUp(self):
        self.old_dir = os.getcwd()

        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

        with io.open(os.path.abspath(".keep"), "w", encoding="utf-8") as fh:
            fh.write("")


    def tearDown(self):
        os.chdir(self.old_dir)
        del self.old_dir

        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir


if __name__ == '__main__':
    unittest.main()
