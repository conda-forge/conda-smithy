import fnmatch
from logging import getLogger
import os
from typing import Iterable


VALID_METAS = ("recipe.yaml",)


def islist(arg, uniform=False, include_dict=True):
    """
    Check whether `arg` is a `list`. Optionally determine whether the list elements
    are all uniform.

    When checking for generic uniformity (`uniform=True`) we check to see if all
    elements are of the first element's type (`type(arg[0]) == type(arg[1])`). For
    any other kinds of uniformity checks are desired provide a uniformity function:

    .. code-block:: pycon
        # uniformity function checking if elements are str and not empty
        >>> truthy_str = lambda e: isinstance(e, str) and e
        >>> islist(["foo", "bar"], uniform=truthy_str)
        True
        >>> islist(["", "bar"], uniform=truthy_str)
        False
        >>> islist([0, "bar"], uniform=truthy_str)
        False

    .. note::
        Testing for uniformity will consume generators.

    :param arg: Object to ensure is a `list`
    :type arg: any
    :param uniform: Whether to check for uniform or uniformity function
    :type uniform: bool, function, optional
    :param include_dict: Whether to treat `dict` as a `list`
    :type include_dict: bool, optional
    :return: Whether `arg` is a `list`
    :rtype: bool
    """
    if isinstance(arg, str) or not isinstance(arg, Iterable):
        # str and non-iterables are not lists
        return False
    elif not include_dict and isinstance(arg, dict):
        # do not treat dict as a list
        return False
    elif not uniform:
        # short circuit for non-uniformity
        return True

    # NOTE: not checking for Falsy arg since arg may be a generator
    # WARNING: if uniform != False and arg is a generator then arg will be consumed

    if uniform is True:
        arg = iter(arg)
        try:
            etype = type(next(arg))
        except StopIteration:
            # StopIteration: list is empty, an empty list is still uniform
            return True
        # check for explicit type match, do not allow the ambiguity of isinstance
        uniform = lambda e: type(e) == etype  # noqa: E731

    try:
        return all(uniform(e) for e in arg)
    except (ValueError, TypeError):
        # ValueError, TypeError: uniform function failed
        return False


def ensure_list(arg, include_dict=True):
    """
    Ensure the object is a list. If not return it in a list.

    :param arg: Object to ensure is a list
    :type arg: any
    :param include_dict: Whether to treat `dict` as a `list`
    :type include_dict: bool, optional
    :return: `arg` as a `list`
    :rtype: list
    """
    if arg is None:
        return []
    elif islist(arg, include_dict=include_dict):
        return list(arg)
    else:
        return [arg]


def rec_glob(path, patterns, ignores=None):
    """
    Recursively searches path for filename patterns.

    :param path: path within to search for files
    :param patterns: list of filename patterns to search for
    :param ignore: list of directory patterns to ignore in search
    :return: list of paths in path satisfying patterns/ignore
    """
    patterns = ensure_list(patterns)
    ignores = ensure_list(ignores)

    for path, dirs, files in os.walk(path):
        # remove directories to ignore
        for ignore in ignores:
            for d in fnmatch.filter(dirs, ignore):
                dirs.remove(d)

        # return filepaths that match a pattern
        for pattern in patterns:
            for f in fnmatch.filter(files, pattern):
                yield os.path.join(path, f)


def find_recipe(path):
    """
    vendored from conda_build.utils to persist same API flow

    recurse through a folder, locating valid meta files (see VALID_METAS).  Raises error if more than one is found.

    Returns full path to meta file to be built.

    If we have a base level meta file and other supplemental (nested) ones, use the base level.
    """
    # if initial path is absolute then any path we find (via rec_glob)
    # will also be absolute
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.join(os.getcwd(), path))

    if os.path.isfile(path):
        if os.path.basename(path) in VALID_METAS:
            return path
        raise OSError(
            "{} is not a valid meta file ({})".format(
                path, ", ".join(VALID_METAS)
            )
        )

    results = list(rec_glob(path, VALID_METAS, ignores=(".AppleDouble",)))

    if not results:
        raise OSError(
            "No meta files ({}) found in {}".format(
                ", ".join(VALID_METAS), path
            )
        )

    if len(results) == 1:
        return results[0]

    # got multiple valid meta files
    # check if a meta file is defined on the base level in which case use that one

    metas = [m for m in VALID_METAS if os.path.isfile(os.path.join(path, m))]
    if len(metas) == 1:
        getLogger(__name__).warn(
            "Multiple meta files found. "
            f"The {metas[0]} file in the base directory ({path}) "
            "will be used."
        )
        return os.path.join(path, metas[0])

    raise OSError(
        "More than one meta files ({}) found in {}".format(
            ", ".join(VALID_METAS), path
        )
    )
