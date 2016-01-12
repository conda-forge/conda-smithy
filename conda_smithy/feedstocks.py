from __future__ import absolute_import
import glob
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
    Return a generator of all cloned feedstock directories.

    """
    pattern = os.path.abspath(os.path.join(feedstocks_directory, '*-feedstock'))
    return sorted(glob.glob(pattern))


def fetch_feedstocks(feedstock_directory):
    for repo_dir in cloned_feedstocks(feedstock_directory):
        repo = Repo(repo_dir)
        print('Fetching for {}'.format(os.path.basename(repo_dir)))
        for remote in repo.remotes:
            try:
                remote.fetch()
            except GitCommandError:
                print("Failed to fetch {} from {}.".format(remote.name, remote.url))


def feedstocks_list_handle_args(args):
   for repo in feedstock_repos(gh_organization):
        print(repo.name)


def feedstocks_clone_all_handle_args(args):
    for repo in feedstock_repos(args.organization):
        clone_directory = os.path.join(args.feedstocks_directory, repo.name)
        if not os.path.exists(clone_directory):
            print('Cloning {}'.format(repo.name))
            new_repo = Repo.init(clone_directory)
            new_repo.clone(repo.ssh_url)
        clone = Repo(clone_directory)
        if 'upstream' in [remote.name for remote in clone.remotes]:
            clone.delete_remote('upstream')
        clone.create_remote('upstream', url=repo.ssh_url)
        

def feedstocks_list_cloned_handle_args(args):
    for feedstock_directory in cloned_feedstocks(args.feedstocks_directory):
        print(os.path.basename(feedstock_directory))


def feedstocks_apply_cloned_handle_args(args):
    import subprocess
    for feedstock_directory in cloned_feedstocks(args.feedstocks_directory):
        feedstock_basename = os.path.basename(feedstock_directory)
        feedstock_package = feedstock_basename.rsplit('-feedstock', 1)[0]
        env = os.environ.copy()
        context = {'FEEDSTOCK_DIRECTORY': feedstock_directory,
                   'FEEDSTOCK_BASENAME': feedstock_basename,
                   'FEEDSTOCK_NAME': feedstock_package}
        env.update(context)
        cmd = [item.format(feedstock_directory, **context) for item in args.cmd]
        print('\nRunning "{}" for {}:'.format(' '.join(cmd), feedstock_package))
        subprocess.check_call(cmd, env=env, cwd=feedstock_directory)


def feedstocks_fetch_handle_args(args):
    return fetch_feedstocks(args.feedstocks_directory)


def feedstocks_fetch_handle_args(args):
    return fetch_feedstocks(args.feedstocks_directory)


def main():
    import argparse

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
