"""
This subpackage contains all linter messages.

To add new linter rules, find the right category in the accompanying modules
and add a new dataclass definition that inherits from `.base.LinterMessage`.
Refer to this base class docstring for more details.

Then, in the linter code, you can add instances of the new dataclass to `lints`
or `hints`. As of v3.62, these containers expect strings, so convert the dataclass
accordingly with `.as_string()`. In the future, we will handle instances natively,
without str conversion.

Once ready, regenerate the JSON docs with `python -m conda_smithy.linter.messages`.
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
