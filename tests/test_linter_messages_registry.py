import dataclasses
import importlib
import inspect
import json
import pkgutil
import re
from collections import defaultdict
from pathlib import Path

import pytest

import conda_smithy.linter.messages as _messages_pkg
from conda_smithy.linter.messages.__main__ import generate_docs
from conda_smithy.linter.messages.base import LinterMessage

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
            obj is LinterMessage
            or not issubclass(obj, LinterMessage)
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
    linter_messages_path = repo_root / "conda_smithy" / "data" / "linter-messages.json"
    on_disk = json.loads(linter_messages_path.read_text().strip())
    assert generate_docs(write=False) == on_disk


def test_no_duplicate_identifiers():
    seen_identifiers = {}
    seen_class_names = {}
    for module in MESSAGE_MODULES:
        for cls in _module_classes_in_source_order(module):
            identifier = cls.identifier
            assert identifier not in seen_identifiers, (
                f"Duplicate identifier {identifier} found "
                f"in {module.__name__}::{cls.__name__}, previously defined in "
                f"{seen_identifiers[identifier].__module__}::"
                f"{seen_identifiers[identifier].__name__}"
            )
            seen_identifiers[identifier] = cls

            assert cls.__name__ not in seen_class_names, (
                f"Duplicate class name {cls.__name__} found "
                f"in {module.__name__}::{cls.__name__}, previously defined in "
                f"{seen_class_names[cls.__name__].__module__}::"
                f"{seen_class_names[cls.__name__].__name__}"
            )
            seen_class_names[cls.__name__] = cls


@pytest.mark.parametrize("module", MESSAGE_MODULES)
def test_message_registry_integrity(module):
    """
    Check that:

    - There are no gaps in identifiers (e.g. [VC-001, VC-003] would fail
      because VC-002 is missing)
    - All identifiers show up in order in the file
    """

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


@pytest.mark.parametrize("module", MESSAGE_MODULES)
def test_message_template_fields_are_valid(module):
    """
    Check that every `${word}` reference in a `message` string corresponds
    to an actual dataclass field on the same class.

    This catches typos and references to non-existent fields: `string.Template`
    uses `safe_substitute`, so unknown `$name` tokens are silently left
    as-is, meaning a misspelled field name would appear verbatim in the
    rendered message shown to users.
    """
    _dollar_brace_re = re.compile(r"\$\{(\w+)\}")

    for cls in _message_classes(module):
        if not dataclasses.is_dataclass(cls):
            continue

        # Skip classes where `message` is a property (dynamic messages).
        if isinstance(inspect.getattr_static(cls, "message", None), property):
            continue

        # Skip classes that override _render_attributes: they control the
        # substitution dict themselves and may inject computed keys that are
        # not dataclass fields (e.g. `dollar` derived from `recipe_version`).
        # TODO: instead of skipping, instantiate the class with zero/default
        # values, call _render_attributes() on the instance, and union its
        # returned keys with field_names so injected keys are also validated.
        if cls._render_attributes is not LinterMessage._render_attributes:
            continue

        message = cls.message
        field_names = {f.name for f in dataclasses.fields(cls)}

        for match in _dollar_brace_re.finditer(message):
            word = match.group(1)
            assert word in field_names, (
                f"'${{{word}}}' in the message of {module.__name__}.{cls.__name__} "
                f"does not match any field of that class. "
                f"Available fields: {sorted(field_names)}. "
                f"If '{{{word}}}' is meant as a literal string, "
                f"remove the '$' (use '{{{word}}}' instead). "
                f"Full message: {message!r}"
            )
