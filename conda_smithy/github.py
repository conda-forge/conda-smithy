from __future__ import absolute_import, print_function

import os
import random
from random import choice

import git
from git import Repo

import github
from github import Github
from github.GithubException import GithubException
from github.Organization import Organization
from github.Team import Team

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


def create_team(org, name, description, repo_names=[]):
    # PyGithub creates secret teams, and has no way of turning that off! :(
    post_parameters = {
        "name": name,
        "description": description,
        "privacy": "closed",
        "permission": "push",
        "repo_names": repo_names
    }
    headers, data = org._requester.requestJsonAndCheck(
        "POST",
        org.url + "/teams",
        input=post_parameters
    )
    return Team(org._requester, headers, data, completed=True)


def add_membership(team, member):
    headers, data = team._requester.requestJsonAndCheck(
        "PUT",
        team.url + "/memberships/" + member
    )
    return (headers, data)


def remove_membership(team, member):
    headers, data = team._requester.requestJsonAndCheck(
        "DELETE",
        team.url + "/memberships/" + member
    )
    return (headers, data)


def has_in_members(team, member):
    status, headers, data = team._requester.requestJson(
        "GET",
        self.url + "/members/" + member
    )
    return status == 204


def get_cached_team(org, team_name, description=""):
    cached_file = os.path.expanduser('~/.conda-smithy/{}-{}-team'.format(org.login, team_name))
    try:
        with open(cached_file, 'r') as fh:
            team_id = int(fh.read().strip())
            return org.get_team(team_id)
    except IOError:
        pass

    team = next((team for team in org.get_teams() if team.name == team_name), None)
    if not team:
        team = create_team(org, team_name, description, [])

    with open(cached_file, 'w') as fh:
        fh.write(str(team.id))

    return team


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

    if args.add_teams:
        if isinstance(user_or_org, Organization):
            configure_github_team(meta, gh_repo)


def configure_github_team(meta, gh_repo):

    # Add a team for this repo and add the maintainers to it.
    superlative = [
        'awesome', 'slick', 'formidable', 'awe-inspiring',
        'breathtaking', 'magnificent', 'wonderous', 'stunning',
        'astonishing', 'superb', 'splendid', 'impressive',
        'unbeatable', 'excellent', 'top', 'outstanding', 'exalted',
        'standout', 'smashing'
    ]

    maintainers = set(
        meta.meta.get('extra', {}).get('recipe-maintainers', [])
    )

    team_name = meta.name()
    # Try to get team or create it if it doesn't exist.
    team = next((team for team in gh_repo.get_teams() if team.name == team_name), None)
    current_maintainers = []
    if not team:
        team = create_team(
            user_or_org,
            team_name,
            'The {} {} contributors!'.format(
                choice(superlative), team_name
            )
        )
        team.add_to_repos(gh_repo)
    else:
        current_maintainers = team.get_members()


    # Add only the new maintainers to the team.
    current_maintainers_handles = set([
        e.login.lower() for e in current_maintainers
    ])
    for new_maintainer in maintainers - current_maintainers_handles:
        add_membership(team, new_maintainer)

    # Mention any maintainers that need to be removed (unlikely here).
    for old_maintainer in current_maintainers_handles - maintainers:
        print(
            "AN OLD MEMBER ({}) NEEDS TO BE REMOVED FROM {}".format(
                old_maintainer, repo_name
            )
        )

    # Get the all-members team
    team_name = 'all-members'
    description = "All of the awesome {} contributors!".format(user_or_org.name)
    all_members_team = get_cached_team(user_or_org, team_name, description)
    new_conda_forge_members = set()

    # Add new members to all-members
    for new_member in maintainers - current_maintainers_handles:
        if not has_in_members(all_members_team, new_member):
            print(
                "Adding a new member ({}) to {}. Welcome! :)".format(
                    new_member, user_or_org.name
                )
            )
            add_membership(all_members_team, new_member)
            new_conda_forge_members.add(new_member)

    return maintainers, current_maintainers_handles, new_conda_forge_members
