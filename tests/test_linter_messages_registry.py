import importlib
import inspect
import pkgutil
import re
from collections import defaultdict
from pathlib import Path

import pytest

import conda_smithy.linter.messages as _messages_pkg
from conda_smithy.linter.messages.__main__ import generate_docs
from conda_smithy.linter.messages.base import _BaseMessage

_EXCLUDED_MODULES = {"base", "__main__"}


def _generate_message_modules():
    _message_modules = []
    for mod in pkgutil.iter_modules(_messages_pkg.__path__):
        if mod.name not in _EXCLUDED_MODULES:
            _message_modules.append(
                importlib.import_module(f"{_messages_pkg.__name__}.{mod.name}")
            )
    return _message_modules


MESSAGE_MODULES = _generate_message_modules()

IDENTIFIER_RE = re.compile(r"^(?P<prefix>[A-Z0-9]+)-(?P<number>\d{3})$")


def _message_classes(module):
    message_classes = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if not (
            obj is _BaseMessage
            or not issubclass(obj, _BaseMessage)
            or obj.__module__ != module.__name__
        ):
            message_classes.append(obj)
    return message_classes


def _module_classes_in_source_order(module):
    def definition_line_number(cls):
        return inspect.getsourcelines(cls)[1]

    classes = _message_classes(module)
    classes.sort(key=definition_line_number)
    return [cls for cls in classes]


def test_linter_docs_up_to_date():
    """
    If this test fails, run 'python -m conda_smithy.linter.messages' to regenerate.
    """
    repo_root = Path(__file__).parent.parent
    linter_docs_path = repo_root / "LINTER.md"
    original_linter_docs = linter_docs_path.read_text()
    assert generate_docs("").strip() == original_linter_docs.strip()


@pytest.mark.parametrize("module", MESSAGE_MODULES)
def test_message_registry_integrity(module):
    """
    Check that:

    - No duplicate identifiers
    - There are no gaps in identifiers (e.g. VC-001 and VC-003 would fail
      because VC-002 is missing)
    - All identifiers show up in order in the file
    """
    seen_identifiers = {}

    classes = _module_classes_in_source_order(module)

    grouped_numbers = defaultdict(list)
    for cls in classes:
        identifier = cls.identifier
        match = IDENTIFIER_RE.match(identifier)
        assert match is not None, (
            "Identifier does not match expected "
            "pattern PREFIX-xxx: "
            f"{identifier} in {module.__name__}::{cls.__name__}"
        )

        prefix = match.group("prefix")
        number = int(match.group("number"))

        assert prefix in module.CATEGORIES, (
            f"Identifier prefix {prefix} is not "
            "registered in CATEGORIES "
            f"(found in {module.__name__}::{cls.__name__}: {identifier})"
        )

        assert identifier not in seen_identifiers, (
            f"Duplicate identifier {identifier} found "
            f"in {module.__name__}::{cls.__name__}, previously defined in "
            f"{seen_identifiers[identifier].__module__}::"
            f"{seen_identifiers[identifier].__name__}"
        )
        seen_identifiers[identifier] = cls

        grouped_numbers[prefix].append(number)

    # Verify identifiers are sorted within each prefix group
    for prefix, numbers in grouped_numbers.items():
        expected_numbers = sorted(numbers)
        assert numbers == expected_numbers, (
            f"Identifiers for prefix {prefix} in "
            f"{module.__name__} are not sorted: {[f'{prefix}-{num:03d}' for num in numbers]},"
        )

    # Verify identifier sequences have no gaps within each prefix group
    for prefix, numbers in grouped_numbers.items():
        numbers = sorted(numbers)
        expected = list(range(numbers[0], numbers[-1] + 1))
        assert numbers == expected, (
            f"Identifier sequence has gaps for "
            f"prefix {prefix} in "
            f"{module.__name__}::{cls.__name__}: "
            f"found {numbers}, expected {expected}"
        )
