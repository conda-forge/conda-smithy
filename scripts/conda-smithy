#!/usr/bin/env python
from __future__ import print_function
import os
import requests
import subprocess
import sys

from conda_build.metadata import MetaData

import conda_smithy.configure_circle_ci as configure_circle_ci
import conda_smithy.configure_feedstock as configure_feedstock


def generate_feedstock_content(target_directory, recipe_dir):
    target_recipe_dir = os.path.join(target_directory, 'recipe')
    if not os.path.exists(target_recipe_dir):
        os.makedirs(target_recipe_dir)
    configure_feedstock.copytree(recipe_dir, target_recipe_dir)

    forge_yml = os.path.join(target_directory, 'conda-forge.yml')
    with open(forge_yml, 'w') as fh:
        fh.write('[]')

    configure_feedstock.main(target_directory)


def init_git_repo(target):
    subprocess.check_call(['git', 'init'], cwd=target)


def create_git_repo(target, meta):
    init_git_repo(target)
    subprocess.check_call(['git', 'add', '*'], cwd=target)
    msg = 'Initial commit of the {} feedstock.'.format(meta.name())
    subprocess.check_call(['git', 'commit', '-m', msg], cwd=target)


class Subcommand(object):
    #: The name of the subcommand
    subcommand = None
    def __init__(self, parser):
        subcommand_parser = parser.add_parser(self.subcommand)
        subcommand_parser.set_defaults(subcommand_func=self)
        return subcommand_parser

    def __call__(self, args):
        pass


class Init(Subcommand):
    subcommand = 'init'
    def __init__(self, parser):
        # conda-smithy init /path/to/udunits-recipe ./
        subcommand_parser = Subcommand.__init__(self, parser)
        subcommand_parser.add_argument("recipe_directory")
        subcommand_parser.add_argument("--feedstock-directory",
                                       default='./{package.name}-feedstock')
        subcommand_parser.add_argument("--no-git-repo", action='store_true',
                                       default=False)

    def __call__(self, args):
        meta = MetaData(args.recipe_directory)
        feedstock_directory = args.feedstock_directory.format(package=argparse.Namespace(name=meta.name()))
        generate_feedstock_content(feedstock_directory, args.recipe_directory)
        if not args.no_git_repo:
            create_git_repo(feedstock_directory, meta)


class GithubCreate(Subcommand):
    subcommand = 'github-create'
    def __init__(self, parser):
        #  conda-smithy github-create ./ --organization=conda-forge
        subcommand_parser = Subcommand.__init__(self, parser)
        subcommand_parser.add_argument("feedstock_directory")
        group = subcommand_parser.add_mutually_exclusive_group()
        group.add_argument("--user")
        group.add_argument("--organization", default="conda-forge")

    def __call__(self, args):
        with open(os.path.expanduser('~/.conda-smithy/github.token'), 'r') as fh:
            token = fh.read().strip()
        meta = configure_feedstock.meta_of_feedstock(args.feedstock_directory)

        from github import Github
        gh = Github(token)
        if args.user is not None:
            pass
            # User has been defined, and organization has not.
            user_or_org.get_user(args.user)
        else:
            # Use the organization provided.
            user_or_org = gh.get_organization(args.organization)
        repo = user_or_org.create_repo(os.path.basename(args.feedstock_directory),
                                       has_wiki=False,
                                       description='A conda-smithy repository for {}.'.format(meta.name()))
        print('Created {} on github'.format(repo.full_name))


class RegisterFeedstockCI(Subcommand):
    subcommand = 'register-feedstock-ci'
    def __init__(self, parser):
        # conda-smithy register-feedstock-ci ./
        subcommand_parser = Subcommand.__init__(self, parser)
        subcommand_parser.add_argument("feedstock_directory")
        group = subcommand_parser.add_mutually_exclusive_group()
        group.add_argument("--user")
        group.add_argument("--organization", default="conda-forge")

    def add_project_to_appveyor(self, user, project):
        headers = {'Authorization': 'Bearer {}'.format(appveyor_token),
                   'Content-Type': 'application/json'}
        url = 'https://ci.appveyor.com/api/projects'

        data = {'repositoryProvider': 'gitHub', 'repositoryName': '{}/{}'.format(user, project)}

        response = requests.post(url, headers=headers, data=data)
        response = requests.get(url, headers=headers)
        if response.status_code != 201:
            response.raise_for_status()

    def __call__(self, args):
        owner = args.user or args.organization
        repo = os.path.basename(os.path.abspath(args.feedstock_directory))

        print('CI Summary for {}/{} (may take some time):'.format(owner, repo))
        configure_circle_ci.add_project_to_circle(owner, repo)
        configure_circle_ci.add_project_to_appveyor(owner, repo)
        configure_circle_ci.add_project_to_travis(owner, repo)


if __name__ == '__main__':
#     UX: 
#         conda-smithy init /path/to/udunits-recipe ./
#         conda-smithy github-create ./ --organization=conda-forge --remote-name=upstream
#         conda-smithy register-feedstock-ci ./

#      How about:
#         conda smithy config
#         conda smithy create-forge ./recipe

#        conda smithy clone-all

    import argparse

    parser = argparse.ArgumentParser("conda-smithy - conda recipe building, made powerful.")
    subparser = parser.add_subparsers()
    # TODO: Consider allowing plugins/extensions using entry_points.
    # http://reinout.vanrees.org/weblog/2010/01/06/zest-releaser-entry-points.html
    for subcommand in Subcommand.__subclasses__():
        subcommand(subparser)

    if not sys.argv[1:]:
#         args = parser.parse_args(['--help'])
        args = parser.parse_args(['init', '../udunits-feedstock/recipe',
                                  '--feedstock-directory=../{package.name}-delme-feedstock'])
#         args = parser.parse_args(['github-create', '../udunits-delme-feedstock'])
#         args = parser.parse_args(['register-feedstock-ci', '../udunits-delme-feedstock'])
    else:
        args = parser.parse_args()

    args.subcommand_func(args)
