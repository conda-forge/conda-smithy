from __future__ import absolute_import
import argparse
import glob
import multiprocessing
import os

from git import Repo, GitCommandError
from github import Github

from . import github as smithy_github


def feedstock_repos(gh_organization):
    token = smithy_github.gh_token()
    gh = Github(token)
    org = gh.get_organization(gh_organization)
    repos = []
    for repo in org.get_repos():
        if repo.name.endswith('-feedstock'):
            repo.package_name = repo.name.rsplit('-feedstock', 1)[0]
            repos.append(repo)
    return sorted(repos, key=lambda repo: repo.name.lower())


def cloned_feedstocks(feedstocks_directory):
    """
    Return a generator of all cloned feedstocks.
    The feedstock will be generated as an argparse.Namespace and can be used:

        for feedstock in cloned_feedstocks(path_to_feedstocks_directory):
            print(feedstock.name)  # The name of the feedstock, e.g. conda-smithy-feedstock
            print(feedstock.package)  # The name of the package within the feedstock, e.g. conda-smithy
            print(feedstock.directory)  # The absolute path to the repo

    """
    pattern = os.path.abspath(os.path.join(feedstocks_directory, '*-feedstock'))
    for feedstock_dir in sorted(glob.glob(pattern)):
        feedstock_basename = os.path.basename(feedstock_dir)
        feedstock_package = feedstock_basename.rsplit('-feedstock', 1)[0]
        feedstock = argparse.Namespace(name=feedstock_basename,
                                       package=feedstock_package,
                                       directory=feedstock_dir)
        yield feedstock


def fetch_feedstock(repo_dir):
    """Git fetch --all a single git repository."""
    repo = Repo(repo_dir)
    for remote in repo.remotes:
        try:
            remote.fetch()
        except GitCommandError:
            print("Failed to fetch {} from {}.".format(remote.name, remote.url))


def fetch_feedstocks(feedstock_directory):
    """
    Do a git fetch on all of the cloned feedstocks.

    Note: This function uses multiprocessing to parallelise the fetch process.

    """
    feedstocks = list(cloned_feedstocks(feedstock_directory))
    # We pick the minimum of ncpus x10 and total feedstocks for the pool size.
    n_processes = min([len(feedstocks), multiprocessing.cpu_count() * 10])
    pool = multiprocessing.Pool(n_processes)
    for repo in cloned_feedstocks(feedstock_directory):
        repo_dir = repo.directory
        pool.apply_async(fetch_feedstock, args=(repo_dir, ))
    pool.close()
    pool.join()


def feedstocks_list_handle_args(args):
   for repo in feedstock_repos(gh_organization):
        print(repo.name)


def clone_all(gh_org, feedstocks_dir):
    for repo in feedstock_repos(gh_org):
        clone_directory = os.path.join(feedstocks_dir, repo.name)
        if not os.path.exists(clone_directory):
            print('Cloning {}'.format(repo.name))
            new_repo = Repo.clone_from(repo.ssh_url, clone_directory)
        clone = Repo(clone_directory)
        if 'upstream' in [remote.name for remote in clone.remotes]:
            clone.delete_remote('upstream')
        clone.create_remote('upstream', url=repo.ssh_url)


def feedstocks_clone_all_handle_args(args):
    return clone_all(args.organization, args.feedstocks_directory)


def feedstocks_list_cloned_handle_args(args):
    for feedstock in cloned_feedstocks(args.feedstocks_directory):
        print(os.path.basename(feedstock.directory))


def feedstocks_apply_cloned_handle_args(args):
    import subprocess
    for feedstock in cloned_feedstocks(args.feedstocks_directory):
        env = os.environ.copy()
        context = {'FEEDSTOCK_DIRECTORY': feedstock.directory,
                   'FEEDSTOCK_BASENAME': feedstock.name,
                   'FEEDSTOCK_NAME': feedstock.package}
        env.update(context)
        cmd = [item.format(feedstock.directory, feedstock=feedstock, **context) for item in args.cmd]
        print('\nRunning "{}" for {}:'.format(' '.join(cmd), feedstock.package))
        subprocess.check_call(cmd, env=env, cwd=feedstock.directory)


def feedstocks_fetch_handle_args(args):
    return fetch_feedstocks(args.feedstocks_directory)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    list_feedstocks = subparsers.add_parser('list', help='List all of the feedstocks available on the GitHub organization.')
    list_feedstocks.set_defaults(func=feedstocks_list_handle_args)
    list_feedstocks.add_argument("--organization", default="conda-forge")

    clone_feedstocks = subparsers.add_parser('clone', help='Clone all of the feedstocks available on the GitHub organization.')
    clone_feedstocks.set_defaults(func=feedstocks_clone_all_handle_args)
    clone_feedstocks.add_argument("--organization", default="conda-forge")
    clone_feedstocks.add_argument("--feedstocks-directory", default="./")

    list_cloned_feedstocks = subparsers.add_parser('list-cloned', help='List all of the feedstocks which have been cloned.')
    list_cloned_feedstocks.set_defaults(func=feedstocks_list_cloned_handle_args)
    list_cloned_feedstocks.add_argument("--feedstocks-directory", default="./")

    apply_cloned_feedstocks = subparsers.add_parser('apply-cloned', help='Apply a subprocess to all of the all feedstocks which have been cloned.')
    apply_cloned_feedstocks.set_defaults(func=feedstocks_apply_cloned_handle_args)
    apply_cloned_feedstocks.add_argument("--feedstocks-directory", default="./")
    apply_cloned_feedstocks.add_argument('cmd', nargs='+',
                                         help=('Command arguments, expanded by FEEDSTOCK_NAME, FEEDSTOCK_DIRECTORY, FEEDSTOCK_BASENAME '
                                               'env variables, run with the cwd set to the feedstock.'))

    fetch_feedstocks = subparsers.add_parser('fetch', help='Run git fetch on all of the cloned feedstocks.')
    fetch_feedstocks.set_defaults(func=feedstocks_fetch_handle_args)
    fetch_feedstocks.add_argument("--feedstocks-directory", default="./")

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    main()
