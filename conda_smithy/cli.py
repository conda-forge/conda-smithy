from __future__ import print_function, absolute_import

import os
import requests
import subprocess
import sys
import argparse

from conda_build.metadata import MetaData

from . import ci_register
from . import configure_feedstock
from . import lint_recipe


def generate_feedstock_content(target_directory, recipe_dir):
    target_recipe_dir = os.path.join(target_directory, 'recipe')
    if not os.path.exists(target_recipe_dir):
        os.makedirs(target_recipe_dir)
    configure_feedstock.copytree(recipe_dir, target_recipe_dir)

    forge_yml = os.path.join(target_directory, 'conda-forge.yml')
    if not os.path.exists(forge_yml):
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
    def __init__(self, parser, help=None):
        subcommand_parser = parser.add_parser(self.subcommand, help=help)
        subcommand_parser.set_defaults(subcommand_func=self)
        return subcommand_parser

    def __call__(self, args):
        pass


class Init(Subcommand):
    subcommand = 'init'
    def __init__(self, parser):
        # conda-smithy init /path/to/udunits-recipe ./
        subcommand_parser = Subcommand.__init__(self, parser, "Create a feedstock git repository.")
        subcommand_parser.add_argument("recipe_directory")
        subcommand_parser.add_argument("--feedstock-directory",
                                       default='./{package.name}-feedstock')
        subcommand_parser.add_argument("--no-git-repo", action='store_true',
                                       default=False)

    def __call__(self, args):
        if not os.path.isdir(args.recipe_directory):
            raise IOError("The recipe directory should be the directory of the conda-recipe. Got {}".format(args.recipe_directory))
        meta = MetaData(args.recipe_directory)
        feedstock_directory = args.feedstock_directory.format(package=argparse.Namespace(name=meta.name()))
        generate_feedstock_content(feedstock_directory, args.recipe_directory)
        if not args.no_git_repo:
            create_git_repo(feedstock_directory, meta)


class GithubCreate(Subcommand):
    subcommand = 'github-create'
    def __init__(self, parser):
        #  conda-smithy github-create ./ --organization=conda-forge
        subcommand_parser = Subcommand.__init__(self, parser, "Create a github repo for a feedstock")
        subcommand_parser.add_argument("feedstock_directory")
        group = subcommand_parser.add_mutually_exclusive_group()
        group.add_argument("--user")
        group.add_argument("--organization", default="conda-forge")
        subcommand_parser.add_argument("--remote-name", default="upstream",
                                       help="The name of the remote to add to the local repo (default: upstream). "
                                            "An empty string will disable adding of a remote.")

    def __call__(self, args):
        from . import github
        github.create_github_repo(args)


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

        print('CI Summary for {}/{} (can take ~30s):'.format(owner, repo))
        ci_register.add_project_to_travis(owner, repo)
        ci_register.travis_token_update_conda_forge_config(args.feedstock_directory, owner, repo)
        ci_register.add_project_to_circle(owner, repo)
        ci_register.add_token_to_circle(owner, repo)
        ci_register.add_project_to_appveyor(owner, repo)


def main():
#     UX:
#         conda-smithy init /path/to/udunits-recipe ./
#         conda-smithy github-create ./ --organization=conda-forge --remote-name=upstream
#         conda-smithy register-feedstock-ci ./

#      How about:
#         conda smithy config
#         conda smithy create-forge ./recipe

#        conda smithy clone-all

    parser = argparse.ArgumentParser("a tool to help create, administer and manage feedstocks")
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


class RecipeLint(Subcommand):
    subcommand = 'recipe-lint'
    def __init__(self, parser):
        subcommand_parser = Subcommand.__init__(self, parser)
        subcommand_parser.add_argument("recipe_directory", default=[os.getcwd()], nargs='*')

    def __call__(self, args):
        all_good = True 
        for recipe in args.recipe_directory:
            lint = lint_recipe.main(os.path.join(recipe))
            if lint:
                all_good = False
                print('{} has some lint:\n  {}'.format(recipe, '\n  '.join(lint)))
            else:
                print('{} is in fine form'.format(recipe))
        # Exit code 1 for some lint, 0 for no lint.
        sys.exit(int(not all_good))


class Rerender(Subcommand):
    subcommand = 'rerender'
    def __init__(self, parser):
        # conda-smithy render /path/to/udunits-recipe
        subcommand_parser = Subcommand.__init__(self, parser)
        subcommand_parser.add_argument("--feedstock_directory", default=os.getcwd())

    def __call__(self, args):
        configure_feedstock.main(args.feedstock_directory)


class Regenerate(Subcommand):
    # A poor-man's alias for rerender.
    subcommand = 'regenerate'
    def __init__(self, parser):
        # conda-smithy render /path/to/udunits-recipe
        subcommand_parser = Subcommand.__init__(self, parser)
        subcommand_parser.add_argument("--feedstock_directory", default=os.getcwd())

    def __call__(self, args):
        configure_feedstock.main(args.feedstock_directory)


if __name__ == '__main__':
    main()
