from contextlib import contextmanager
import os
import shutil


def get_repo(path, search_parent_directories=True):
    repo = None
    try:
        import git
        repo = git.Repo(
            path,
            search_parent_directories=search_parent_directories
        )
    except ImportError:
        pass
    except git.InvalidGitRepositoryError:
        pass

    return repo


def get_file_blob(repo, filename):
    idx = repo.index
    rel_filepath = os.path.relpath(filename, repo.working_dir)
    blob = idx.iter_blobs(lambda _: _[1].path == rel_filepath).next()[1]
    return blob


def get_mode_file(filename):
    repo = get_repo(filename)
    if repo:
        blob = get_file_blob(repo, filename)
        mode = blob.mode
    else:
        mode = os.stat(filename).st_mode

    return mode


def set_mode_file(filename, mode):
    repo = get_repo(filename)
    if repo:
        blob = get_file_blob(repo, filename)
        blob.mode |= mode
        repo.index.add([blob])

    os.chmod(filename, mode)


@contextmanager
def write_file(filename):
    with open(filename, "w") as fh:
        yield fh

    repo = get_repo(filename)
    if repo:
        repo.index.add([filename])


def remove_file(filename):
    if os.path.exists(filename):
        repo = get_repo(filename)
        if repo:
            repo.index.remove([filename])

        os.remove(filename)


def copy_file(src, dst):
    shutil.copy2(src, dst)

    repo = get_repo(dst)
    if repo:
        repo.index.add([dst])
