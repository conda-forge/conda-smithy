import datetime
import json
import os
import re
import shutil
import tempfile
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Union

import jinja2
import jinja2.sandbox
import ruamel.yaml
from conda_build.api import render as conda_build_render
from conda_build.config import Config
from conda_build.render import MetaData
from rattler_build_conda_compat.render import MetaData as RattlerBuildMetaData
from ruamel.yaml.representer import RoundTripRepresenter

RATTLER_BUILD = "rattler-build"
CONDA_BUILD = "conda-build"
SET_PYTHON_MIN_RE = re.compile(r"{%\s+set\s+python_min\s+=")


class _LiteralScalarString(ruamel.yaml.scalarstring.LiteralScalarString):
    __slots__ = ("comment", "lc")


class _FoldedScalarString(ruamel.yaml.scalarstring.FoldedScalarString):
    __slots__ = ("fold_pos", "comment", "lc")


class _DoubleQuotedScalarString(
    ruamel.yaml.scalarstring.DoubleQuotedScalarString
):
    __slots__ = "lc"


class _SingleQuotedScalarString(
    ruamel.yaml.scalarstring.SingleQuotedScalarString
):
    __slots__ = "lc"


class _PlainScalarString(ruamel.yaml.scalarstring.PlainScalarString):
    __slots__ = "lc"


PreservedScalarString = _LiteralScalarString


class _ScalarInt(ruamel.yaml.scalarint.ScalarInt):
    lc = None


class _DecimalInt(ruamel.yaml.scalarint.DecimalInt):
    lc = None


class _ScalarBoolean(ruamel.yaml.scalarbool.ScalarBoolean):
    lc = None


class _ScalarFloat(ruamel.yaml.scalarfloat.ScalarFloat):
    lc = None


class _ExponentialFloat(ruamel.yaml.scalarfloat.ExponentialFloat):
    lc = None


class _ExponentialCapsFloat(ruamel.yaml.scalarfloat.ExponentialCapsFloat):
    lc = None

class _WithLineNumberConstructor(ruamel.yaml.constructor.RoundTripConstructor):
    """Round trip constructor that keeps line numbers for most elements.

    Adapted from: https://stackoverflow.com/questions/45716281/parsing-yaml-get-line-numbers-even-in-ordered-maps
    """

    def __init__(self, preserve_quotes=None, loader=None):
        super().__init__(preserve_quotes=preserve_quotes, loader=loader)
        if not hasattr(self.loader, "comment_handling"):
            self.loader.comment_handling = None

    def _update_lc(self, node, value):
        value.lc = ruamel.yaml.comments.LineCol()
        value.lc.line = node.start_mark.line
        value.lc.col = node.start_mark.column
        return value

    def construct_scalar(self, node):
        ret_val = None
        if node.style == '|' and isinstance(node.value, str):
            lss = _LiteralScalarString(node.value, anchor=node.anchor)
            if self.loader and self.loader.comment_handling is None:
                if node.comment and node.comment[1]:
                    lss.comment = node.comment[1][0]  # type: ignore
            else:
                # NEWCMNT
                if node.comment is not None and node.comment[1]:
                    # nprintf('>>>>nc1', node.comment)
                    # EOL comment after |
                    lss.comment = self.comment(node.comment[1][0])  # type: ignore
            ret_val = lss
        elif node.style == '>' and isinstance(node.value, str):
            fold_positions = []  # type: List[int]
            idx = -1
            while True:
                idx = node.value.find('\a', idx + 1)
                if idx < 0:
                    break
                fold_positions.append(idx - len(fold_positions))
            fss = _FoldedScalarString(node.value.replace('\a', ''), anchor=node.anchor)
            if self.loader and self.loader.comment_handling is None:
                if node.comment and node.comment[1]:
                    fss.comment = node.comment[1][0]  # type: ignore
            else:
                # NEWCMNT
                if node.comment is not None and node.comment[1]:
                    # nprintf('>>>>nc2', node.comment)
                    # EOL comment after >
                    fss.comment = self.comment(node.comment[1][0])  # type: ignore
            if fold_positions:
                fss.fold_pos = fold_positions  # type: ignore
            ret_val = fss
        elif bool(self._preserve_quotes) and isinstance(node.value, str):
            if node.style == "'":
                ret_val = _SingleQuotedScalarString(node.value, anchor=node.anchor)
            if node.style == '"':
                ret_val = _DoubleQuotedScalarString(node.value, anchor=node.anchor)
        if not ret_val:
            if node.anchor:
                ret_val = _PlainScalarString(node.value, anchor=node.anchor)
            else:
                ret_val = _PlainScalarString(node.value)
        return self._update_lc(node, ret_val)

    def construct_yaml_int(self, node: Any) -> Any:
        super_value = super().construct_yaml_int(node)
        if isinstance(super_value, ruamel.yaml.scalarint.DecimalInt):
            ret_val = _DecimalInt(super_value, anchor=node.anchor)
        else:
            ret_val = _ScalarInt(super_value, anchor=node.anchor)
        if isinstance(super_value, ruamel.yaml.scalarint.ScalarInt):
            ret_val.__dict__.update(super_value.__dict__)
        return self._update_lc(node, ret_val)

    def construct_yaml_float(self, node: Any) -> Any:
        super_value = super().construct_yaml_float(node)
        if isinstance(super_value, ruamel.yaml.scalarfloat.ExponentialFloat):
            ret_val = _ExponentialFloat(super_value, anchor=node.anchor)
        elif isinstance(super_value, ruamel.yaml.scalarfloat.ExponentialCapsFloat):
            ret_val = _ExponentialCapsFloat(super_value, anchor=node.anchor)
        else:
            ret_val = _ScalarFloat(super_value, anchor=node.anchor)
        if isinstance(super_value, ruamel.yaml.scalarfloat.ScalarFloat):
            ret_val.__dict__.update(super_value.__dict__)
        return self._update_lc(node, ret_val)

    def construct_yaml_bool(self, node: Any) -> Any:
        super_value = super().construct_yaml_bool(node)
        ret_val = _ScalarBoolean(super_value, anchor=node.anchor)
        if isinstance(super_value, ruamel.yaml.scalarbool.ScalarBoolean):
            ret_val.__dict__.update(super_value.__dict__)
        return self._update_lc(node, ret_val)


def _get_metadata_from_feedstock_dir(
    feedstock_directory: Union[str, os.PathLike],
    forge_config: dict[str, Any],
    conda_forge_pinning_file: Union[str, os.PathLike, None] = None,
) -> Union[MetaData, RattlerBuildMetaData]:
    """
    Return either the conda-build metadata or rattler-build metadata from the feedstock directory
    based on conda_build_tool value from forge_config.
    Raises OsError if no meta.yaml or recipe.yaml is found in feedstock_directory.
    """
    if forge_config and forge_config.get("conda_build_tool") == RATTLER_BUILD:
        meta = RattlerBuildMetaData(
            feedstock_directory,
        )
    else:
        if conda_forge_pinning_file:
            config = Config(
                variant_config_files=[conda_forge_pinning_file],
            )
        else:
            config = None
        meta = conda_build_render(
            feedstock_directory,
            config=config,
            finalize=False,
            bypass_env_check=True,
            trim_skip=False,
        )[0][0]

    return meta


def get_feedstock_name_from_meta(
    meta: Union[MetaData, RattlerBuildMetaData],
) -> str:
    """Get the feedstock name from a parsed meta.yaml or recipe.yaml."""
    if "feedstock-name" in meta.meta["extra"]:
        return meta.meta["extra"]["feedstock-name"]
    elif "parent_recipe" in meta.meta["extra"]:
        return meta.meta["extra"]["parent_recipe"]["name"]
    else:
        return meta.name()


def get_feedstock_about_from_meta(meta) -> dict:
    """Fetch the feedstock about from the parsed meta.yaml."""
    # it turns out that conda_build would not preserve the feedstock about:
    #   - if a subpackage does not have about, it uses the feedstock's
    #   - if a subpackage has about, it's used as is
    # therefore we need to parse the yaml again just to get the about section...
    if "parent_recipe" in meta.meta["extra"]:
        recipe_meta = os.path.join(
            meta.meta["extra"]["parent_recipe"]["path"], "meta.yaml"
        )
        with open(recipe_meta, encoding="utf-8") as fh:
            content = render_meta_yaml("".join(fh))
            meta = get_yaml().load(content)
        return dict(meta["about"])
    else:
        # no parent recipe for any reason, use self's about
        return dict(meta.meta["about"])


def get_yaml(allow_duplicate_keys: bool = True):
    # define global yaml API
    # roundrip-loader and allowing duplicate keys
    # for handling # [filter] / # [not filter]
    # Don't use a global variable for this as a global
    # variable will make conda-smithy thread unsafe.
    yaml = ruamel.yaml.YAML(typ="rt")
    yaml.allow_duplicate_keys = allow_duplicate_keys
    yaml.Constructor = _WithLineNumberConstructor
    # re-add so that we override the parent class' default constructor
    yaml.Constructor.add_default_constructor("int")
    yaml.Constructor.add_default_constructor("float")
    yaml.Constructor.add_default_constructor("bool")
    yaml.Constructor.allow_duplicate_keys = allow_duplicate_keys
    # needed for representers
    RoundTripRepresenter.add_representer(
        _LiteralScalarString,
        RoundTripRepresenter.represent_literal_scalarstring,
    )
    RoundTripRepresenter.add_representer(
        _FoldedScalarString, RoundTripRepresenter.represent_folded_scalarstring
    )
    RoundTripRepresenter.add_representer(
        _SingleQuotedScalarString,
        RoundTripRepresenter.represent_single_quoted_scalarstring,
    )
    RoundTripRepresenter.add_representer(
        _DoubleQuotedScalarString,
        RoundTripRepresenter.represent_double_quoted_scalarstring,
    )
    RoundTripRepresenter.add_representer(
        _PlainScalarString, RoundTripRepresenter.represent_plain_scalarstring
    )
    RoundTripRepresenter.add_representer(
        _ScalarInt, RoundTripRepresenter.represent_scalar_int
    )
    # RoundTripRepresenter.add_representer(BinaryInt, RoundTripRepresenter.represent_binary_int)
    # RoundTripRepresenter.add_representer(OctalInt, RoundTripRepresenter.represent_octal_int)
    # RoundTripRepresenter.add_representer(HexInt, RoundTripRepresenter.represent_hex_int)
    # RoundTripRepresenter.add_representer(HexCapsInt, RoundTripRepresenter.represent_hex_caps_int)
    RoundTripRepresenter.add_representer(
        _ScalarFloat, RoundTripRepresenter.represent_scalar_float
    )
    RoundTripRepresenter.add_representer(
        _ScalarBoolean, RoundTripRepresenter.represent_scalar_bool
    )
    return yaml


@contextmanager
def tmp_directory():
    tmp_dir = tempfile.mkdtemp("_recipe")
    yield tmp_dir
    shutil.rmtree(tmp_dir)


class NullUndefined(jinja2.Undefined):
    def __str__(self):
        return self._undefined_name

    def __getattr__(self, name):
        return f"{self}.{name}"

    def __getitem__(self, name):
        return f'{self}["{name}"]'


class MockOS(dict):
    def __init__(self):
        self.environ = defaultdict(str)
        self.sep = "/"


def stub_compatible_pin(*args, **kwargs):
    return f"compatible_pin {args[0]}"


def stub_subpackage_pin(*args, **kwargs):
    return f"subpackage_pin {args[0]}"


def _munge_python_min(text):
    new_lines = []
    for line in text.splitlines(keepends=True):
        if SET_PYTHON_MIN_RE.match(line):
            line = "{% set python_min = '9999' %}\n"
        new_lines.append(line)
    return "".join(new_lines)


def render_meta_yaml(text):
    env = jinja2.sandbox.SandboxedEnvironment(undefined=NullUndefined)

    # stub out cb3 jinja2 functions - they are not important for linting
    #    if we don't stub them out, the ruamel.yaml load fails to interpret them
    #    we can't just use conda-build's api.render functionality, because it would apply selectors
    env.globals.update(
        dict(
            compiler=lambda x: x + "_compiler_stub",
            stdlib=lambda x: x + "_stdlib_stub",
            pin_subpackage=stub_subpackage_pin,
            pin_compatible=stub_compatible_pin,
            cdt=lambda *args, **kwargs: "cdt_stub",
            load_file_regex=lambda *args, **kwargs: defaultdict(str),
            load_file_data=lambda *args, **kwargs: defaultdict(str),
            load_setup_py_data=lambda *args, **kwargs: defaultdict(str),
            load_str_data=lambda *args, **kwargs: defaultdict(str),
            datetime=datetime,
            time=time,
            target_platform="linux-64",
            build_platform="linux-64",
            mpi="mpi",
            python_min="9999",  # use as a sentinel value for linting
        )
    )
    mockos = MockOS()
    py_ver = "3.7"
    context = {"os": mockos, "environ": mockos.environ, "PY_VER": py_ver}
    content = env.from_string(_munge_python_min(text)).render(context)
    return content


@contextmanager
def update_conda_forge_config(forge_yaml):
    """Utility method used to update conda forge configuration files

    Usage:
    >>> with update_conda_forge_config(somepath) as cfg:
    ...     cfg['foo'] = 'bar'
    """
    if os.path.exists(forge_yaml):
        with open(forge_yaml, encoding="utf-8") as fh:
            code = get_yaml().load(fh)
    else:
        code = {}

    # Code could come in as an empty list.
    if not code:
        code = {}

    yield code

    get_yaml().dump(code, Path(forge_yaml))


def merge_dict(src, dest):
    """Recursive merge dictionary"""
    for key, value in src.items():
        if isinstance(value, dict):
            # get node or create one
            node = dest.setdefault(key, {})
            merge_dict(value, node)
        else:
            dest[key] = value

    return dest


def _json_default(obj):
    """Accept sets for JSON"""
    if isinstance(obj, set):
        return sorted(obj)
    else:
        return obj


class HashableDict(dict):
    """Hashable dict so it can be in sets"""

    def __hash__(self):
        return hash(json.dumps(self, sort_keys=True, default=_json_default))
