from __future__ import absolute_import

import os

import git
from git import Repo

import github
from github import Github
from github.GithubException import GithubException

from . import configure_feedstock


def gh_token():
    try:
        with open(os.path.expanduser('~/.conda-smithy/github.token'), 'r') as fh:
            token = fh.read().strip()
    except IOError:
        msg = ('No github token. Go to https://github.com/settings/tokens/new and generate\n'
               'a token with repo access. Put it in ~/.conda-smithy/github.token')
        raise RuntimeError(msg)
    return token


def create_github_repo(args):
    token = gh_token()
    meta = configure_feedstock.meta_of_feedstock(args.feedstock_directory)

    gh = Github(token)
    user_or_org = None
    if args.user is not None:
        pass
        # User has been defined, and organization has not.
        user_or_org = gh.get_user()
    else:
        # Use the organization provided.
        user_or_org = gh.get_organization(args.organization)

    repo_name = '{}-feedstock'.format(meta.name())
    try:
        gh_repo = user_or_org.create_repo(repo_name, has_wiki=False,
                                          description='A conda-smithy repository for {}.'.format(meta.name()))
        print('Created {} on github'.format(gh_repo.full_name))
    except GithubException as gh_except:
        if gh_except.data.get('errors', [{}])[0].get('message', '') != u'name already exists on this account':
            raise
        gh_repo = user_or_org.get_repo(repo_name)
        print('Github repository already exists.')

    # Now add this new repo as a remote on the local clone.
    repo = Repo(args.feedstock_directory)
    remote_name = args.remote_name.strip()
    if remote_name:
        if remote_name in [remote.name for remote in repo.remotes]:
            existing_remote = repo.remotes[remote_name]
            if existing_remote.url != gh_repo.ssh_url:
                print("Remote {} already exists, and doesn't point to {} "
                      "(it points to {}).".format(remote_name, gh_repo.ssh_url, existing_remote.url))
        else:
            repo.create_remote(remote_name, gh_repo.ssh_url)
