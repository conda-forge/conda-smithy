"""
This subpackage contains all linter messages. To add new linter rules,
find the right category in the accompanying modules and add a new dataclass
definition. Identifier must be unique across the whole subpackage.

Once ready, regenerate the docs with `python -m conda_smithy.linter.messages`.
"""

from conda_smithy.linter.messages import (
    conda_forge,
    feedstock_config,
    recipe,
    recipe_variants,
)

# Short aliases for imports
cf = conda_forge
fc = feedstock_config
r = recipe
rv = recipe_variants

all_modules = [cf, fc, r, rv]
