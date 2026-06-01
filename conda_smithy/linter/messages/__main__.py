import json
from pathlib import Path


def generate_docs(write: bool = True) -> dict[str, object]:
    """
    Generate a JSON file with static information about all messages.

    The returned object is a dict with two keys:
    - `categories`: maps category identifiers to descriptions:
    - `messages`: an array of `LinterMessage.dump()` dicts.
    """
    from conda_smithy.linter.messages import all_modules
    from conda_smithy.linter.messages.base import LinterMessage
    from conda_smithy.linter.messages.conda_forge import (
        CATEGORIES as CONDA_FORGE_CATEGORIES,
    )
    from conda_smithy.linter.messages.feedstock_config import (
        CATEGORIES as FEEDSTOCK_CONFIG_CATEGORIES,
    )
    from conda_smithy.linter.messages.recipe import CATEGORIES as RECIPE_CATEGORIES
    from conda_smithy.linter.messages.recipe_variants import (
        CATEGORIES as RECIPE_CONFIG_CATEGORIES,
    )

    def collect_messages():
        for module in all_modules:
            for obj_name in dir(module):
                if obj_name.startswith("_") or obj_name == "LinterMessage":
                    continue
                try:
                    obj = getattr(module, obj_name)
                    if issubclass(obj, LinterMessage):
                        yield obj
                except TypeError:
                    pass

    dumped = {
        "categories": {
            **CONDA_FORGE_CATEGORIES,
            **FEEDSTOCK_CONFIG_CATEGORIES,
            **RECIPE_CATEGORIES,
            **RECIPE_CONFIG_CATEGORIES,
        },
        "messages": [
            MessageCls.dump()
            for MessageCls in sorted(collect_messages(), key=lambda msg: msg.identifier)
        ],
    }
    if write:
        Path(__file__).parents[2].joinpath("data", "linter-messages.json").write_text(
            json.dumps(dumped, indent=2) + "\n"
        )
    return dumped


if __name__ == "__main__":
    import sys

    generate_docs()
    sys.exit()
