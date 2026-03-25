"""
This subpackage contains all linter messages. To add new linter rules,
find the right category in the accompanying modules and add a new dataclass
definition. Identifier must be unique across the whole subpackage.

Once ready, regenerate the docs with `python -m conda_smithy.linter.messages`.
"""

from conda_smithy.linter.messages.conda_forge import *  # noqa: F403
from conda_smithy.linter.messages.feedstock_config import *  # noqa: F403
from conda_smithy.linter.messages.recipe import *  # noqa: F403
from conda_smithy.linter.messages.recipe_variants import *  # noqa: F403
