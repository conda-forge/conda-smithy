from __future__ import print_function, absolute_import

import os
import requests
import subprocess
import sys
import time
import argparse

import conda
from distutils.version import LooseVersion
from conda_build.metadata import MetaData

from . import configure_feedstock
from . import feedstock_io
from . import lint_recipe
from . import __version__


PY2 = sys.version_info[0] == 2

def generate_feedstock_content(target_directory, source_recipe_dir, meta):
    target_directory = os.path.abspath(target_directory)
    recipe_dir = "recipe"
    target_recipe_dir = os.path.join(target_directory, recipe_dir)
    if not os.path.exists(target_recipe_dir):
        os.makedirs(target_recipe_dir)
    # If there is a source recipe, copy it now to the right dir
    if source_recipe_dir:
        try:
            configure_feedstock.copytree(source_recipe_dir, target_recipe_dir)
        except Exception as e:
            import sys
            raise type(e)(
                str(e) + ' while copying file %s' % source_recipe_dir
                ).with_traceback(sys.exc_info()[2])

    forge_yml = os.path.join(target_directory, 'conda-forge.yml')
    if not os.path.exists(forge_yml):
        with feedstock_io.write_file(forge_yml) as fh:
            fh.write(u"[]")

    cwd = os.getcwd()
    os.chdir(target_directory)
    try:
        configure_feedstock.main(target_directory)
    finally:
        os.chdir(cwd)


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
        msg = 'Initial feedstock commit with conda-smithy {}.'.format(__version__)

        try:
            os.makedirs(feedstock_directory)
            if not args.no_git_repo:
                subprocess.check_call(['git', 'init'], cwd=feedstock_directory)
            generate_feedstock_content(feedstock_directory, args.recipe_directory, meta)
            if not args.no_git_repo:
                subprocess.check_call(['git', 'commit', '-m', msg], cwd=feedstock_directory)

            print("\nRepository created, please edit conda-forge.yml to configure the upload channels\n"
                  "and afterwards call 'conda smithy register-github'")
        except RuntimeError as e:
            print(e)


class RegisterGithub(Subcommand):
    subcommand = 'register-github'
    def __init__(self, parser):
        #  conda-smithy register-github ./ --organization=conda-forge
        super(RegisterGithub, self).__init__(parser, "Register a repo for a feedstock at github.")
        scp = self.subcommand_parser
        scp.add_argument("--add-teams",
                         action='store_true',
                         default=False,
                         help="Create teams and register maintainers to them.")
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
            print(e)


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
        from conda_smithy import ci_register
        owner = args.user or args.organization
        repo = os.path.basename(os.path.abspath(args.feedstock_directory))

        print('CI Summary for {}/{} (can take ~30s):'.format(owner, repo))
        try:
            ci_register.add_project_to_travis(owner, repo)
            ci_register.travis_token_update_conda_forge_config(args.feedstock_directory, owner, repo)
            time.sleep(1)
            ci_register.travis_configure(owner, repo)
            ci_register.add_project_to_circle(owner, repo)
            ci_register.add_token_to_circle(owner, repo)
            ci_register.add_project_to_appveyor(owner, repo)
            ci_register.appveyor_encrypt_binstar_token(args.feedstock_directory, owner, repo)
            ci_register.appveyor_configure(owner, repo)
            ci_register.add_conda_forge_webservice_hooks(owner, repo)
            print("\nCI services have been enabled. You may wish to regenerate the feedstock.\n"
                  "Any changes will need commiting to the repo.")
        except RuntimeError as e:
            print(e)

class Regenerate(Subcommand):
    subcommand = 'regenerate'
    aliases = ['rerender']
    def __init__(self, parser):
        super(Regenerate, self).__init__(parser, "Regenerate / update the CI support files of the "
                                               "feedstock.")
        scp = self.subcommand_parser
        scp.add_argument("--feedstock_directory", default=os.getcwd(),
                         help="The directory of the feedstock git repository.")
        scp.add_argument("-c", "--commit", nargs='?', choices=["edit", "auto"], const="edit",
                         help="Whether to setup a commit or not.")

    def __call__(self, args):
        try:
            configure_feedstock.main(args.feedstock_directory)
            print("\nRe-rendered with conda-smithy %s.\n" % __version__)

            is_git_repo = os.path.exists(os.path.join(args.feedstock_directory, ".git"))
            if is_git_repo:
                has_staged_changes = subprocess.call(
                    [
                        "git", "diff", "--cached", "--quiet", "--exit-code"
                    ],
                    cwd=args.feedstock_directory
                )
                if has_staged_changes:
                    if args.commit:
                        git_args = [
                            'git',
                            'commit',
                            '-m',
                            'MNT: Re-rendered with conda-smithy %s' % __version__
                        ]
                        if args.commit == "edit":
                            git_args += [
                                '--edit',
                                '--status',
                                '--verbose'
                            ]
                        subprocess.check_call(
                            git_args,
                            cwd=args.feedstock_directory
                        )
                        print("")
                    else:
                        print(
                            'You can commit the changes with:\n\n'
                            '    git commit -m "MNT: Re-rendered with conda-smithy %s"\n' % __version__
                        )
                    print("These changes need to be pushed to github!\n")
                else:
                    print("No changes made. This feedstock is up-to-date.\n")
        except RuntimeError as e:
            print(e)
        except subprocess.CalledProcessError as e:
            print(e)


class RecipeLint(Subcommand):
    subcommand = 'recipe-lint'
    def __init__(self, parser):
        super(RecipeLint, self).__init__(parser, "Lint a single conda recipe.")
        scp = self.subcommand_parser
        scp.add_argument("--conda-forge", action='store_true')
        scp.add_argument("recipe_directory", default=[os.getcwd()], nargs='*')

    def __call__(self, args):
        all_good = True
        for recipe in args.recipe_directory:
            lint = lint_recipe.main(os.path.join(recipe), conda_forge=args.conda_forge)
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

    parser.add_argument('--version', action='version',
                        version=__version__,
                        help="Show conda-smithy's version, and exit.")

    if not sys.argv[1:]:
        args = parser.parse_args(['--help'])
    else:
        args = parser.parse_args()

    # Check conda version for compatibility
    if LooseVersion(conda.__version__) >= LooseVersion('4.4'):
        print('You appear to be using conda {}, but conda-smithy {} is\ncurrently only compatible with conda versions < 4.4.'.format(
            conda.__version__, __version__))
        sys.exit(2)

    args.subcommand_func(args)


if __name__ == '__main__':
    main()
