"""Variant algebras

This set of utilities are used to compose conda-build variants in a consistent way in
order to facilitate storing migration state within recipes rather than relying on
global state stored in something like `conda-forge-pinning`

The primary function to run here is ``variant_add`` that will add two variant configs
together and produce a desired outcome.

For full details on how this is supposed to work see CFEP-9

https://github.com/conda-forge/conda-forge-enhancement-proposals/pull/13

"""

from functools import partial
from typing import Any, Dict, List, Optional, Union

import conda_build.variants as variants
import toolz
import yaml
from conda.exports import VersionOrder
from conda_build.config import Config
from conda_build.utils import ensure_list


def parse_variant(
    variant_file_content: str, config: Optional[Config] = None
) -> Dict[
    str,
    Union[
        List[str],
        float,
        List[List[str]],
        Dict[str, Dict[str, str]],
        Dict[str, Dict[str, List[str]]],
    ],
]:
    """
    Parameters
    ----------
    variant_file_content : str
        The loaded variant contents.  This can include selectors etc.
    """
    if not config:
        from conda_build.config import Config

        config = Config()
    from conda_build.metadata import ns_cfg, select_lines

    contents = select_lines(
        variant_file_content, ns_cfg(config), variants_in_place=False
    )
    content = yaml.load(contents, Loader=yaml.loader.BaseLoader) or {}
    variants.trim_empty_keys(content)
    # TODO: Base this default on mtime or something
    content["migrator_ts"] = float(content.get("migrator_ts", -1.0))
    return content


def _version_order(
    v: Union[str, float], ordering: Optional[List[str]] = None
) -> Union[int, VersionOrder, float]:
    if ordering is not None:
        return ordering.index(v)
    else:
        if isinstance(v, str):
            v = v.replace(" ", ".").replace("*", "1")
        try:
            return VersionOrder(v)
        except Exception:
            return v


def variant_key_add(
    k: str,
    v_left: Union[List[str], List[float]],
    v_right: Union[List[str], List[float]],
    ordering: Optional[List[str]] = None,
) -> Union[List[str], List[float]]:
    """Version summation adder.

    This takes the higher version of the two things.
    """
    out_v = []
    common_length = min(len(v_left), len(v_right))
    for i in range(common_length):
        e_l, e_r = v_left[i], v_right[i]
        if _version_order(e_l, ordering) < _version_order(e_r, ordering):
            out_v.append(e_r)
        else:
            out_v.append(e_l)
    # Tail items
    for vs in (v_left, v_right):
        if len(vs) > common_length:
            out_v.extend(vs[common_length:])

    return out_v


def variant_key_replace(k, v_left, v_right):
    return v_right


def variant_key_set_merge(k, v_left, v_right, ordering=None):
    """Merges two sets in order, preserving common keys"""
    out_v = set(v_left) & set(v_right)
    return sorted(out_v, key=partial(_version_order, ordering=ordering))


def variant_key_set_union(k, v_left, v_right, ordering=None):
    """Merges two sets in order, preserving all keys"""
    out_v = set(v_left) | set(v_right)
    return sorted(out_v, key=partial(_version_order, ordering=ordering))


def op_variant_key_add(v1: dict, v2: dict):
    """Operator for performing a key-add

    key-add is additive so you will end up with more entries in the resulting dictionary
    This will append a the version specied by the primary_key migrator field.

    Additionally all dependencies specified by zip_keys will be updated with additional
    entries from v2.

    If an ordering reorders the primary key all the zip_keys referring to that primary key will also
    be reodered in the same manner.

    additional_zip_keys can be specified to either create a new zip_key or
    add additional keys to the zip_key keyset containing the primary key
    """
    primary_key = v2["__migrator"]["primary_key"]
    additional_zip_keys = v2["__migrator"].get("additional_zip_keys", [])

    ordering = v2["__migrator"].get("ordering", {})
    if primary_key not in v2:
        return v1
    if primary_key not in v1:
        raise RuntimeError("unhandled")

    newly_added_zip_keys = set()

    result = v1.copy()

    if additional_zip_keys:
        for chunk in result.get("zip_keys", []):
            zip_keyset = set(chunk)
            if primary_key in zip_keyset:
                # The primary is already part of some zip_key, add the additional keys
                for additional_key in additional_zip_keys:
                    if additional_key not in zip_keyset:
                        chunk.append(additional_key)
                        newly_added_zip_keys.add(additional_key)
                break
        else:
            # The for loop didn't break thus the primary is not part of any zip_key,
            # create a new one including the primary key
            result.setdefault("zip_keys", []).append(
                [primary_key] + additional_zip_keys
            )
            newly_added_zip_keys.update([primary_key] + additional_zip_keys)

    for key in newly_added_zip_keys:
        # store the default value for the key, so that subsequent
        # key additions don't need to specify them and continue to use the default value
        # assert len(v1[key]) == 1
        result.setdefault("__additional_zip_keys_default_values", {})[
            additional_key
        ] = result[additional_key][0]

    for pkey_ind, pkey_val in enumerate(v2[primary_key]):
        # object is present already, ignore everything
        if pkey_val in result[primary_key]:
            continue

        new_keys = variant_key_set_union(
            None,
            result[primary_key],
            [pkey_val],
            ordering=ordering.get(primary_key),
        )
        position_map = {
            i: new_keys.index(v) for i, v in enumerate(result[primary_key])
        }

        result[primary_key] = new_keys
        new_key_position = new_keys.index(pkey_val)

        # handle zip_keys
        for chunk in result.get("zip_keys", []):
            zip_keyset = frozenset(chunk)
            if primary_key in zip_keyset:
                for key in zip_keyset:
                    if key == primary_key:
                        continue

                    # Transform key to zip_key if required
                    if key in newly_added_zip_keys:
                        default_value = result[
                            "__additional_zip_keys_default_values"
                        ][key]
                        result[key] = [default_value] * len(new_keys)

                    # Create a new version of the key from
                    # assert len(v2[key]) == 1
                    new_value = [None] * len(new_keys)
                    for i, j in position_map.items():
                        new_value[j] = result[key][i]

                    if key in v2:
                        new_value[new_key_position] = v2[key][pkey_ind]
                    elif key in result.get(
                        "__additional_zip_keys_default_values", {}
                    ):
                        new_value[new_key_position] = result[
                            "__additional_zip_keys_default_values"
                        ][key]

                    result[key] = new_value

    return result


def op_variant_key_remove(v1: dict, v2: dict):
    """Inverse of op_variant_key_add

    Will remove a given value from the field identified by primary_key and associated
    zip_keys
    """
    primary_key = v2["__migrator"]["primary_key"]
    ordering = v2["__migrator"].get("ordering", {})
    if primary_key not in v2:
        return v1
    assert len(v2[primary_key]) == 1
    result = v1.copy()
    if primary_key not in v1:
        return v1
    if v2[primary_key][0] not in v1[primary_key]:
        return v1
    new_keys = variant_key_set_union(
        None, v1[primary_key], [], ordering=ordering.get(primary_key)
    )
    new_keys.remove(v2[primary_key][0])
    position_map = {
        i: v1[primary_key].index(v) for i, v in enumerate(new_keys)
    }
    result[primary_key] = new_keys

    # handle zip_keys
    for chunk in v1.get("zip_keys", []):
        zip_keyset = frozenset(chunk)
        if primary_key in zip_keyset:
            for key in zip_keyset:
                if key == primary_key:
                    continue
                # Create a new version of the key from, using the order from the primary key
                new_value = [None] * len(new_keys)
                for i, j in position_map.items():
                    new_value[i] = v1[key][j]
                result[key] = new_value

    return result


VARIANT_OP = {
    "key_add": op_variant_key_add,
    "key_remove": op_variant_key_remove,
}


def variant_add(v1: dict, v2: dict) -> Dict[str, Any]:
    """Adds the two variants together.

    Present this assumes mostly flat dictionaries.

    TODO:
        - Add support for special sums like replace
    """
    left = set(v1.keys()).difference(v2.keys())
    right = set(v2.keys()).difference(v1.keys())
    joint = set(v1.keys()) & set(v2.keys())

    # deal with __migrator: ordering
    if "__migrator" in v2:
        ordering = v2["__migrator"].get("ordering", {})
        operation = v2["__migrator"].get("operation")
        # handle special operations
        if operation:
            return VARIANT_OP[operation](v1, v2)
    else:
        ordering = {}

    # special keys
    if "__migrator" in right:
        right.remove("__migrator")

    # special keys in joint
    special_variants = {}
    if "pin_run_as_build" in joint:
        # For run_as_build we enforce the migrator's pin
        # TODO: should this just be a normal ordering merge, favoring more exact pins?
        joint.remove("pin_run_as_build")
        special_variants["pin_run_as_build"] = {
            **v1["pin_run_as_build"],
            **v2["pin_run_as_build"],
        }

    if "zip_keys" in joint:
        # zip_keys is a bit weird to join on as we don't have a particularly good way of identifying
        # a block.  Longer term having these be named blocks would make life WAY simpler
        # That does require changes to conda-build itself though
        #
        # A zip_keys block is deemed mergeable if zkₛ,ᵢ ⊂ zkₘ,ᵢ
        zk_out = []
        zk_l = {frozenset(e) for e in v1["zip_keys"]}
        zk_r = {frozenset(e) for e in v2["zip_keys"]}

        for zk_r_i in sorted(zk_r, key=lambda x: -len(x)):
            for zk_l_i in sorted(zk_l, key=lambda x: -len(x)):
                # Merge the longest common zk first
                if zk_l_i.issubset(zk_r_i):
                    zk_l.remove(zk_l_i)
                    zk_r.remove(zk_r_i)
                    zk_out.append(zk_r_i)
                    break
            else:
                # Nothing to do
                pass

        zk_out.extend(zk_l)
        zk_out.extend(zk_r)
        zk_out = sorted(
            [sorted(zk) for zk in zk_out], key=lambda x: (len(x), str(x))
        )

        joint.remove("zip_keys")
        special_variants["zip_keys"] = zk_out

    joint_variant = {}
    for k in joint:
        v_left, v_right = ensure_list(v1[k]), ensure_list(v2[k])
        joint_variant[k] = variant_key_add(
            k, v_left, v_right, ordering=ordering.get(k, None)
        )

    out = {
        **toolz.keyfilter(lambda k: k in left, v1),
        **toolz.keyfilter(lambda k: k in right, v2),
        **joint_variant,
        **special_variants,
    }

    return out
