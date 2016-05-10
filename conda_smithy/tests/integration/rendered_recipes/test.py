import os
import subprocess
import unittest


class Test_custom_matrix(unittest.TestCase):
    priors = {}
#    for fname in ['appveyor.yml', 'ci_scripts/run_docker_build.sh', '.travis.yml']:
    feedstock_dir = os.path.join(os.path.dirname(__file__), 'custom_matrix')
    child = subprocess.Popen(['conda-smithy', 'rerender', '--feedstock_directory', feedstock_dir],
                             stdout=subprocess.PIPE)
    out, _ = child.communicate()
#    self.assertEqual(child.returncode, 0, out)
    # TODO: Make some assertions.

class Test_np_dep(unittest.TestCase):
    feedstock_dir = os.path.join(os.path.dirname(__file__), 'np_dep')
    child = subprocess.Popen(['conda-smithy', 'rerender', '--feedstock_directory', feedstock_dir],
                             stdout=subprocess.PIPE)
    out, _ = child.communicate()


if __name__ == '__main__':
    unittest.main()
