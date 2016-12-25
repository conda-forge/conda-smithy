import os
import json

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

parent_dir = os.path.dirname(os.path.realpath(__file__))
pin_path = os.path.join(parent_dir, 'pinning.json')

with open(pin_path) as pin_handle:
    pinning = json.load(pin_handle)
