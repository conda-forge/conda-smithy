"""Variant algebras

This set of utilities are used to compose conda-build variants in a consistent way in
order to facilitate storing migration state within recipes rather than relying on
global state stored in something like `conda-forge-pinning`

The primary function to run here is ``variant_add`` that will add two variant configs
together and produce a desired outcome.

For full details on how this is supposed to work see CFEP-9

https://github.com/conda-forge/conda-forge-enhancement-proposals/pull/13

"""

import yaml
import toolz
from conda_build.utils import ensure_list
import conda_build.variants as variants
from conda.exports import VersionOrder
from conda_build.config import Config
from functools import partial


from typing import Any, Dict, List, Optional, Union


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
        The loaded vaiant contents.  This can include selectors etc.
    """
    if not config:
        from conda_build.config import Config

        config = Config()
    from conda_build.metadata import select_lines, ns_cfg

    contents = select_lines(
        variant_file_content, ns_cfg(config), variants_in_place=False
    )
    content = yaml.load(contents, Loader=yaml.loader.BaseLoader) or {}
    variants.trim_empty_keys(content)
    # TODO: Base this default on mtime or something
    content["migration_ts"] = float(content.get("migration_ts", -1.0))
    return content


def _version_order(
    v: Union[str, float], ordering: Optional[List[str]] = None
) -> Union[int, VersionOrder, float]:
    if ordering is not None:
        return ordering.index(v)
    else:
        try:
            return VersionOrder(v)
        except:
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
    """Merges two sets in order"""
    out_v = set(v_left) & set(v_right)
    return sorted(out_v, key=partial(_version_order, ordering=ordering))


def variant_add(v1: dict, v2: dict) -> Dict[str, Any]:
    """Adds the two variants together.

    Present this assumes mostly flat dictionaries.

    TODO:
        - Add support for special sums like replace
        - Add delete_key support
    """
    left = set(v1.keys()).difference(v2.keys())
    right = set(v2.keys()).difference(v1.keys())
    joint = set(v1.keys()) & set(v2.keys())

    # deal with __migrator: ordering
    if "__migrator" in v2:
        print(v2)
        ordering = v2["__migrator"].get("ordering", {})
        print(ordering)
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
        # A zip_keys block is deemend mergeable if zkₛ,ᵢ ⊂ zkₘ,ᵢ
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
