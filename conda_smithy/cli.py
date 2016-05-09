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


PY2 = sys.version_info[0] == 2

def generate_feedstock_content(target_directory, source_recipe_dir, meta):
    recipe_dir = "recipe"
    target_recipe_dir = os.path.join(target_directory, recipe_dir)
    if not os.path.exists(target_recipe_dir):
        os.makedirs(target_recipe_dir)
    # If there is a source recipe, copy it now to the right dir
    if source_recipe_dir:
        configure_feedstock.copytree(source_recipe_dir, target_recipe_dir)

    forge_yml = os.path.join(target_directory, 'conda-forge.yml')
    if not os.path.exists(forge_yml):
        with open(forge_yml, 'w') as fh:
            fh.write('[]')

    configure_feedstock.main(target_directory)


def init_git_repo(target):
    subprocess.check_call(['git', 'init'], cwd=target)


def create_git_repo(target, msg):
    init_git_repo(target)
    subprocess.check_call(['git', 'add', '*'], cwd=target)
    if sys.platform == "win32":
        # prevent this:
        # bash: line 1: ./ci_support/run_docker_build.sh: Permission denied
        # ./ci_support/run_docker_build.sh returned exit code 126
        subprocess.check_call(['git', 'update-index', '--chmod=+x', 'ci_support/run_docker_build.sh'], cwd=target)
    subprocess.check_call(['git', 'commit', '-m', msg], cwd=target)


class Subcommand(object):
    #: The name of the subcommand
    subcommand = None
    aliases = []
    def __init__(self, parser, help=None):
        if PY2:
            # aliases not allowed in 2.7 :-(
            subcommand_parser = parser.add_parser(self.subcommand, help=help)
        else:
            subcommand_parser = parser.add_parser(self.subcommand, help=help, aliases=self.aliases)

        subcommand_parser.set_defaults(subcommand_func=self)
        self.subcommand_parser = subcommand_parser

    def __call__(self, args):
        pass


class Init(Subcommand):
    subcommand = 'init'
    def __init__(self, parser):
        # conda-smithy init /path/to/udunits-recipe ./

        super(Init, self).__init__(parser, "Create a feedstock git repository, which can contain "
                                           "one conda recipes.")
        scp = self.subcommand_parser
        scp.add_argument("recipe_directory", help="The path to the source recipe directory.")
        scp.add_argument("--feedstock-directory", default='./{package.name}-feedstock',
                        help="Target directory, where the new feedstock git repository should be "
                             "created. (Default: './<packagename>-feedstock')")
        scp.add_argument("--no-git-repo", action='store_true',
                                       default=False,
                                       help="Do not init the feedstock as a git repository.")

    def __call__(self, args):
        # check some error conditions
        if args.recipe_directory and not os.path.isdir(args.recipe_directory):
            raise IOError("The source recipe directory should be the directory of the "
                          "conda-recipe you want to build a feedstock for. Got {}".format(
                args.recipe_directory))

        # Get some information about the source recipe.
        if args.recipe_directory:
            meta = MetaData(args.recipe_directory)
        else:
            meta = None

        feedstock_directory = args.feedstock_directory.format(package=argparse.Namespace(name=meta.name()))
        msg = 'Initial commit of the {} feedstock.'.format(meta.name())

        try:
            generate_feedstock_content(feedstock_directory, args.recipe_directory, meta)
            if not args.no_git_repo:
                create_git_repo(feedstock_directory, msg)

            print("\nRepository created, please edit conda-forge.yml to configure the upload channels\n"
                  "and afterwards call 'conda smithy register-github'")
        except RuntimeError as e:
            print(e.message)


class RegisterGithub(Subcommand):
    subcommand = 'register-github'
    def __init__(self, parser):
        #  conda-smithy register-github ./ --organization=conda-forge
        super(RegisterGithub, self).__init__(parser, "Register a repo for a feedstock at github.")
        scp = self.subcommand_parser
        scp.add_argument("feedstock_directory",
                         help="The directory of the feedstock git repository.")
        group = scp.add_mutually_exclusive_group()
        group.add_argument("--user", help="github username under which to register this repo")
        group.add_argument("--organization", default="conda-forge",
                           help="github organisation under which to register this repo")
        scp.add_argument("--remote-name", default="upstream",
                                       help="The name of the remote to add to the local repo (default: upstream). "
                                            "An empty string will disable adding of a remote.")

    def __call__(self, args):
        from . import github
        try:
            github.create_github_repo(args)
            print("\nRepository registered at github, now call 'conda smithy register-ci'")
        except RuntimeError as e:
            print(e.message)


class RegisterCI(Subcommand):
    subcommand = 'register-ci'
    def __init__(self, parser):
        # conda-smithy register-ci ./
        super(RegisterCI, self).__init__(parser, "Register a feedstock at the CI "
                                                              "services which do the builds.")
        scp = self.subcommand_parser
        scp.add_argument("--feedstock_directory", default=os.getcwd(),
                         help="The directory of the feedstock git repository.")
        group = scp.add_mutually_exclusive_group()
        group.add_argument("--user", help="github username under which to register this repo")
        group.add_argument("--organization", default="conda-forge",
                           help="github organisation under which to register this repo")

    def __call__(self, args):
        owner = args.user or args.organization
        repo = os.path.basename(os.path.abspath(args.feedstock_directory))

        print('CI Summary for {}/{} (can take ~30s):'.format(owner, repo))
        try:
            ci_register.add_project_to_travis(owner, repo)
            ci_register.travis_token_update_conda_forge_config(args.feedstock_directory, owner, repo)
            ci_register.add_project_to_circle(owner, repo)
            ci_register.add_token_to_circle(owner, repo)
            ci_register.add_project_to_appveyor(owner, repo)
            ci_register.appveyor_encrypt_binstar_token(args.feedstock_directory, owner, repo)
            ci_register.appveyor_configure(owner, repo)
            ci_register.add_conda_linting(owner, repo)
            print("\nCI services have been enabled enabled. You may wish to regnerate the feedstock.\n"
                  "Any changes will need commiting to the repo.")
        except RuntimeError as e:
            print(e.message)

class Regenerate(Subcommand):
    subcommand = 'regenerate'
    aliases = ['rerender']
    def __init__(self, parser):
        super(Regenerate, self).__init__(parser, "Regenerate / update the CI support files of the "
                                               "feedstock.")
        scp = self.subcommand_parser
        scp.add_argument("--feedstock_directory", default=os.getcwd(),
                         help="The directory of the feedstock git repository.")

    def __call__(self, args):
        try:
            configure_feedstock.main(args.feedstock_directory)
            print("\nCI support files regenerated. These need to be pushed to github!")
        except RuntimeError as e:
            print(e.message)


class RecipeLint(Subcommand):
    subcommand = 'recipe-lint'
    def __init__(self, parser):
        super(RecipeLint, self).__init__(parser, "Lint a single conda recipe.")
        scp = self.subcommand_parser
        scp.add_argument("recipe_directory", default=[os.getcwd()], nargs='*')

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



def main():

    parser = argparse.ArgumentParser("a tool to help create, administer and manage feedstocks.")
    subparser = parser.add_subparsers()
    # TODO: Consider allowing plugins/extensions using entry_points.
    # http://reinout.vanrees.org/weblog/2010/01/06/zest-releaser-entry-points.html
    for subcommand in Subcommand.__subclasses__():
        subcommand(subparser)
    # And the alias for rerender
    if PY2:
        class Rerender(Regenerate):
            # A poor-man's alias for regenerate.
            subcommand = 'rerender'
        Rerender(subparser)

    if not sys.argv[1:]:
        args = parser.parse_args(['--help'])
    else:
        args = parser.parse_args()

    args.subcommand_func(args)


if __name__ == '__main__':
    main()
