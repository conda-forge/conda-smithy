from __future__ import absolute_import

from . import configure_circle_ci, configure_feedstock

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
