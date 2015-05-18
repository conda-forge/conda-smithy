import unittest
import configure_feedstock
from conda_build.metadata import MetaData


class Test_compute_build_matrix(unittest.TestCase):
    def setUp(self):
        self.meta = MetaData.fromdict({'package': {'name': 'test_pkg'},
                                       'requirements': {'build': []}})

    def setdefault(self, field, value, default=None):
        section, key = field.split('/')
        return self.meta.get_section(section).setdefault(key, default)

    def add_requirements(self, *args):
        for arg in args:
            self.setdefault('requirements/build', []).append(arg)

    def test_numpy_no_python(self):
        self.add_requirements('numpy')
        r = configure_feedstock.compute_build_matrix(self.meta)
        print r

    def test_min_numpy(self):
        self.add_requirements('numpy >18', 'python')
        r = configure_feedstock.compute_build_matrix(self.meta)
        print r

    def test_py2(self):
        self.add_requirements('python 2.7')
        matrix = configure_feedstock.compute_build_matrix(self.meta)
        self.assertEqual(matrix, [(('python', '2.7'),)])

    def test_py3(self):
        self.add_requirements('python >=3')
        matrix = configure_feedstock.compute_build_matrix(self.meta)
        self.assertEqual(matrix, [(('python', '3.4'),)])


if __name__ == '__main__':
    unittest.main()