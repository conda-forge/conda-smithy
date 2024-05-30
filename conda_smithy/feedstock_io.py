from contextlib import contextmanager
import io
import os
from pathlib import Path
import shutil
import stat


def get_repo(path, search_parent_directories=True):
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


def get_repo_root(path):
    try:
        return get_repo(path).working_tree_dir
    except AttributeError:
        return None


def set_exe_file(filename, set_exe=True):
    IXALL = stat.S_IXOTH | stat.S_IXGRP | stat.S_IXUSR

    repo = get_repo(filename)
    if repo:
        mode = "+x" if set_exe else "-x"
        repo.git.execute(
            ["git", "update-index", "--chmod=%s" % mode, filename]
        )

    mode = os.stat(filename).st_mode
    if set_exe:
        mode |= IXALL
    else:
        mode -= mode & IXALL
    Path(filename).chmod(mode)


@contextmanager
def write_file(filename):
    dirname = Path(filename).parent
    dirname.mkdir(parents=True, exist_ok=True)

    with io.open(filename, "w", encoding="utf-8", newline="\n") as fh:
        yield fh

    repo = get_repo(filename)
    if repo:
        repo.index.add([filename])


def touch_file(filename):
    with write_file(filename) as fh:
        fh.write("")


def remove_file_or_dir(filename):
    if not Path(filename).is_dir():
        return remove_file(filename)

    repo = get_repo(filename)
    if repo:
        repo.index.remove([filename], r=True)
    shutil.rmtree(filename)


def remove_file(filename):
    touch_file(filename)

    repo = get_repo(filename)
    if repo:
        repo.index.remove([filename])

    Path(filename).unlink()

    dirname = Path(filename).parent
    while dirname.exists() and not any(dirname.iterdir()):
        dirname.rmdir()
        dirname = dirname.parent


def copy_file(src, dst):
    """
    Tried to copy utf-8 text files line-by-line to avoid
    getting CRLF characters added on Windows.

    If the file fails to be decoded with utf-8, we revert to a regular copy.
    """
    try:
        with io.open(src, "r", encoding="utf-8") as fh_src:
            with io.open(dst, "w", encoding="utf-8", newline="\n") as fh_dst:
                for line in fh_src:
                    fh_dst.write(line)
    except UnicodeDecodeError:
        # Leave any other files alone.
        shutil.copy(src, dst)

    shutil.copymode(src, dst)

    repo = get_repo(dst)
    if repo:
        repo.index.add([dst])
