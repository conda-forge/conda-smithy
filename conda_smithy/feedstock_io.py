import os
import shutil
import stat
from contextlib import contextmanager
from io import TextIOWrapper
from typing import Iterator, Optional, Union


def get_repo(path: str, search_parent_directories: bool = True):
    repo = None
    try:
        import git

        repo = git.Repo(
            path, search_parent_directories=search_parent_directories
        )
    except ImportError:
        pass
    except git.InvalidGitRepositoryError:
        pass

    return repo


def get_repo_root(path: str) -> Optional[str]:
    try:
        return get_repo(path).working_tree_dir
    except AttributeError:
        return None


def set_exe_file(filename: str, set_exe: bool = True):
    all_execute_permissions = stat.S_IXOTH | stat.S_IXGRP | stat.S_IXUSR

    repo = get_repo(filename)
    if repo:
        mode: Union[str, int] = "+x" if set_exe else "-x"
        repo.git.execute(["git", "update-index", f"--chmod={mode}", filename])

    mode = os.stat(filename).st_mode
    if set_exe:
        mode |= all_execute_permissions
    else:
        mode -= mode & all_execute_permissions
    os.chmod(filename, mode)


@contextmanager
def write_file(filename: str) -> Iterator[TextIOWrapper]:
    dirname = os.path.dirname(filename)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(filename, "w", encoding="utf-8", newline="\n") as fh:
        yield fh

    repo = get_repo(filename)
    if repo:
        repo.index.add([filename])


def touch_file(filename: str):
    with write_file(filename) as fh:
        fh.write("")


def remove_file_or_dir(filename: str) -> None:
    if not os.path.isdir(filename):
        return remove_file(filename)

    repo = get_repo(filename)
    if repo:
        repo.index.remove([filename], r=True)
    shutil.rmtree(filename)


def remove_file(filename: str):
    touch_file(filename)

    repo = get_repo(filename)
    if repo:
        repo.index.remove([filename])

    os.remove(filename)

    dirname = os.path.dirname(filename)
    if dirname and not os.listdir(dirname):
        os.removedirs(dirname)


def copy_file(src: str, dst: str):
    """
    Tried to copy utf-8 text files line-by-line to avoid
    getting CRLF characters added on Windows.

    If the file fails to be decoded with utf-8, we revert to a regular copy.
    """
    try:
        with open(src, encoding="utf-8") as fh_src:
            with open(dst, "w", encoding="utf-8", newline="\n") as fh_dst:
                for line in fh_src:
                    fh_dst.write(line)
    except UnicodeDecodeError:
        # Leave any other files alone.
        shutil.copy(src, dst)

    shutil.copymode(src, dst)

    repo = get_repo(dst)
    if repo:
        repo.index.add([dst])
