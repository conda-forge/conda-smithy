import os
import shutil
import stat
from contextlib import contextmanager


def get_repo(path):
    repo = None
    try:
        import pygit2

        repo = pygit2.Repository(path)
    except ImportError:
        pass
    except pygit2.GitError:
        pass

    return repo


def get_repo_root(path):
    try:
        return get_repo(path).workdir.rstrip(os.path.sep)
    except AttributeError:
        return None


def set_exe_file(filename, set_exe=True):
    all_execute_permissions = stat.S_IXOTH | stat.S_IXGRP | stat.S_IXUSR

    repo = get_repo(filename)
    if repo:
        index_entry = repo.index[os.path.relpath(filename, repo.workdir)]
        if set_exe:
            index_entry.mode |= all_execute_permissions
        else:
            index_entry.mode &= ~all_execute_permissions
        repo.index.add(index_entry)
        repo.index.write()

    mode = os.stat(filename).st_mode
    if set_exe:
        mode |= all_execute_permissions
    else:
        mode -= mode & all_execute_permissions
    os.chmod(filename, mode)


@contextmanager
def write_file(filename):
    dirname = os.path.dirname(filename)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(filename, "w", encoding="utf-8", newline="\n") as fh:
        yield fh

    repo = get_repo(filename)
    if repo:
        repo.index.add(os.path.relpath(filename, repo.workdir))
        repo.index.write()


def touch_file(filename):
    with write_file(filename) as fh:
        fh.write("")


def remove_file_or_dir(filename):
    if not os.path.isdir(filename):
        return remove_file(filename)

    repo = get_repo(filename)
    if repo:
        repo.index.remove_all(["filename/**"])
        repo.index.write()
    shutil.rmtree(filename)


def remove_file(filename):
    touch_file(filename)

    repo = get_repo(filename)
    if repo:
        try:
            repo.index.remove(os.path.relpath(filename, repo.workdir))
            repo.index.write()
        except OSError:  # this is specifically "file not in index"
            pass

    os.remove(filename)

    dirname = os.path.dirname(filename)
    if dirname and not os.listdir(dirname):
        os.removedirs(dirname)


def copy_file(src, dst):
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
        repo.index.add(os.path.relpath(dst, repo.workdir))
        repo.index.write()
