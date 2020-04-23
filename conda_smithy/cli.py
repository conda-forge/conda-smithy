import os
import subprocess
import sys
import time
import argparse
import io

from textwrap import dedent

import conda
from distutils.version import LooseVersion
from conda_build.metadata import MetaData

from . import configure_feedstock
from . import feedstock_io
from . import lint_recipe
from . import __version__


if sys.version_info[0] == 2:
    raise Exception("Conda-smithy does not support python 2!")


def generate_feedstock_content(target_directory, source_recipe_dir):
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
                str(e) + " while copying file %s" % source_recipe_dir
            ).with_traceback(sys.exc_info()[2])

    forge_yml = os.path.join(target_directory, "conda-forge.yml")
    if not os.path.exists(forge_yml):
        with feedstock_io.write_file(forge_yml) as fh:
            fh.write(u"{}")


class Subcommand(object):
    #: The name of the subcommand
    subcommand = None
    aliases = []

    def __init__(self, parser, help=None):
        subcommand_parser = parser.add_parser(
            self.subcommand, help=help, description=help, aliases=self.aliases
        )
        subcommand_parser.set_defaults(subcommand_func=self)
        self.subcommand_parser = subcommand_parser

    def __call__(self, args):
        pass


class Init(Subcommand):
    subcommand = "init"

    def __init__(self, parser):
        # conda-smithy init /path/to/udunits-recipe ./

        super(Init, self).__init__(
            parser,
            "Create a feedstock git repository, which can contain "
            "one conda recipes.",
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "recipe_directory", help="The path to the source recipe directory."
        )
        scp.add_argument(
            "--feedstock-directory",
            default="./{package.name}-feedstock",
            help="Target directory, where the new feedstock git repository should be "
            "created. (Default: './<packagename>-feedstock')",
        )

    def __call__(self, args):
        # check some error conditions
        if args.recipe_directory and not os.path.isdir(args.recipe_directory):
            raise IOError(
                "The source recipe directory should be the directory of the "
                "conda-recipe you want to build a feedstock for. Got {}".format(
                    args.recipe_directory
                )
            )

        # Get some information about the source recipe.
        if args.recipe_directory:
            meta = MetaData(args.recipe_directory)
        else:
            meta = None

        feedstock_directory = args.feedstock_directory.format(
            package=argparse.Namespace(name=meta.name())
        )
        msg = "Initial feedstock commit with conda-smithy {}.".format(
            __version__
        )

        os.makedirs(feedstock_directory)
        subprocess.check_call(["git", "init"], cwd=feedstock_directory)
        generate_feedstock_content(feedstock_directory, args.recipe_directory)
        subprocess.check_call(
            ["git", "commit", "-m", msg], cwd=feedstock_directory
        )

        print(
            "\nRepository created, please edit conda-forge.yml to configure the upload channels\n"
            "and afterwards call 'conda smithy register-github'"
        )


class RegisterGithub(Subcommand):
    subcommand = "register-github"

    def __init__(self, parser):
        #  conda-smithy register-github ./ --organization=conda-forge
        super(RegisterGithub, self).__init__(
            parser, "Register a repo for a feedstock at github."
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--add-teams",
            action="store_true",
            default=False,
            help="Create teams and register maintainers to them.",
        )
        scp.add_argument(
            "feedstock_directory",
            help="The directory of the feedstock git repository.",
        )
        group = scp.add_mutually_exclusive_group()
        group.add_argument(
            "--user", help="github username under which to register this repo"
        )
        group.add_argument(
            "--organization",
            default="conda-forge",
            help="github organisation under which to register this repo",
        )
        scp.add_argument(
            "--remote-name",
            default="upstream",
            help="The name of the remote to add to the local repo (default: upstream). "
            "An empty string will disable adding of a remote.",
        )
        scp.add_argument(
            "--extra-admin-users",
            nargs="*",
            help="Extra users to be added as admins",
        )

    def __call__(self, args):
        from . import github

        github.create_github_repo(args)
        print(
            "\nRepository registered at github, now call 'conda smithy register-ci'"
        )


class RegisterCI(Subcommand):
    subcommand = "register-ci"

    def __init__(self, parser):
        # conda-smithy register-ci ./
        super(RegisterCI, self).__init__(
            parser,
            "Register a feedstock at the CI " "services which do the builds.",
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--feedstock_directory",
            default=os.getcwd(),
            help="The directory of the feedstock git repository.",
        )
        group = scp.add_mutually_exclusive_group()
        group.add_argument(
            "--user", help="github username under which to register this repo"
        )
        group.add_argument(
            "--organization",
            default="conda-forge",
            help="github organisation under which to register this repo",
        )
        for ci in [
            "Azure",
            "Travis",
            "Circle",
            "Appveyor",
            "Drone",
            "Webservice",
        ]:
            scp.add_argument(
                "--without-{}".format(ci.lower()),
                dest=ci.lower(),
                action="store_false",
                help="If set, {} will be not registered".format(ci),
            )
            default = {ci.lower(): True}
            scp.set_defaults(**default)

    def __call__(self, args):
        from conda_smithy import ci_register

        owner = args.user or args.organization
        repo = os.path.basename(os.path.abspath(args.feedstock_directory))

        print("CI Summary for {}/{} (can take ~30s):".format(owner, repo))
        if args.travis:
            # Assume that the user has enabled travis-ci.com service
            # user-wide or org-wide for all repos
            # ci_register.add_project_to_travis(owner, repo)
            time.sleep(1)
            ci_register.travis_configure(owner, repo)
            ci_register.add_token_to_travis(owner, repo)
            # Assume that the user has enabled travis-ci.com service
            # user-wide or org-wide for all repos
            # ci_register.travis_cleanup(owner, repo)
        else:
            print("Travis registration disabled.")
        if args.circle:
            ci_register.add_project_to_circle(owner, repo)
            ci_register.add_token_to_circle(owner, repo)
        else:
            print("Circle registration disabled.")
        if args.azure:
            from conda_smithy import azure_ci_utils

            if azure_ci_utils.default_config.token is None:
                print(
                    "No azure token. Create a token at https://dev.azure.com/"
                    "conda-forge/_usersSettings/tokens and\n"
                    "put it in ~/.conda-smithy/azure.token"
                )
            ci_register.add_project_to_azure(owner, repo)
        else:
            print("Azure registration disabled.")
        if args.appveyor:
            ci_register.add_project_to_appveyor(owner, repo)
            ci_register.appveyor_encrypt_binstar_token(
                args.feedstock_directory, owner, repo
            )
            ci_register.appveyor_configure(owner, repo)
        else:
            print("Appveyor registration disabled.")

        if args.drone:
            ci_register.add_project_to_drone(owner, repo)
            ci_register.add_token_to_drone(owner, repo)
        else:
            print("Drone registration disabled.")

        if args.webservice:
            ci_register.add_conda_forge_webservice_hooks(owner, repo)
        else:
            print("Heroku webservice registration disabled.")
        print(
            "\nCI services have been enabled. You may wish to regenerate the feedstock.\n"
            "Any changes will need commiting to the repo."
        )


class AddAzureBuildId(Subcommand):
    subcommand = "azure-buildid"

    def __init__(self, parser):
        # conda-smithy azure-buildid ./
        from conda_smithy import azure_ci_utils

        super(AddAzureBuildId, self).__init__(
            parser,
            dedent(
                "Update the azure configuration stored in the config file."
            ),
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--feedstock_directory",
            default=os.getcwd(),
            help="The directory of the feedstock git repository.",
        )
        group = scp.add_mutually_exclusive_group()
        group.add_argument(
            "--user",
            help="azure username for which this repo is enabled already",
        )
        group.add_argument(
            "--organization",
            default=azure_ci_utils.AzureConfig._default_org,
            help="azure organisation for which this repo is enabled already",
        )
        scp.add_argument(
            "--project_name",
            default=azure_ci_utils.AzureConfig._default_project_name,
            help="project name that feedstocks are registered under",
        )

    def __call__(self, args):
        from conda_smithy import azure_ci_utils

        owner = args.user or args.organization
        repo = os.path.basename(os.path.abspath(args.feedstock_directory))

        config = azure_ci_utils.AzureConfig(
            org_or_user=owner, project_name=args.project_name
        )

        build_info = azure_ci_utils.get_build_id(repo, config)

        from .utils import update_conda_forge_config

        with update_conda_forge_config(args.feedstock_directory) as config:
            config.setdefault("azure", {})
            config["azure"]["build_id"] = build_info["build_id"]
            config["azure"]["user_or_org"] = build_info["user_or_org"]
            config["azure"]["project_name"] = build_info["project_name"]
            config["azure"]["project_id"] = build_info["project_id"]


class Regenerate(Subcommand):
    subcommand = "regenerate"
    aliases = ["rerender"]

    def __init__(self, parser):
        super(Regenerate, self).__init__(
            parser,
            "Regenerate / update the CI support files of the " "feedstock.",
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--feedstock_directory",
            default=os.getcwd(),
            help="The directory of the feedstock git repository.",
        )
        scp.add_argument(
            "-c",
            "--commit",
            nargs="?",
            choices=["edit", "auto"],
            const="edit",
            help="Whether to setup a commit or not.",
        )
        scp.add_argument(
            "--no-check-uptodate",
            action="store_true",
            help="Don't check that conda-smithy and conda-forge-pinning are uptodate",
        )
        scp.add_argument(
            "-e",
            "--exclusive-config-file",
            default=None,
            help="Exclusive conda-build config file to replace conda-forge-pinning. "
            + "For advanced usage only",
        )
        scp.add_argument(
            "--check",
            action="store_true",
            default=False,
            help="Check if regenerate can be performed",
        )

    def __call__(self, args):
        configure_feedstock.main(
            args.feedstock_directory,
            no_check_uptodate=args.no_check_uptodate,
            commit=args.commit,
            exclusive_config_file=args.exclusive_config_file,
            check=args.check,
        )


class RecipeLint(Subcommand):
    subcommand = "recipe-lint"

    def __init__(self, parser):
        super(RecipeLint, self).__init__(parser, "Lint a single conda recipe.")
        scp = self.subcommand_parser
        scp.add_argument("--conda-forge", action="store_true")
        scp.add_argument("recipe_directory", default=[os.getcwd()], nargs="*")

    def __call__(self, args):
        all_good = True
        for recipe in args.recipe_directory:
            lints, hints = lint_recipe.main(
                os.path.join(recipe),
                conda_forge=args.conda_forge,
                return_hints=True,
            )
            if lints:
                all_good = False
                print(
                    "{} has some lint:\n  {}".format(
                        recipe, "\n  ".join(lints)
                    )
                )
                if hints:
                    print(
                        "{} also has some suggestions:\n  {}".format(
                            recipe, "\n  ".join(hints)
                        )
                    )
            elif hints:
                print(
                    "{} has some suggestions:\n  {}".format(
                        recipe, "\n  ".join(hints)
                    )
                )
            else:
                print("{} is in fine form".format(recipe))
        # Exit code 1 for some lint, 0 for no lint.
        sys.exit(int(not all_good))


POST_SKELETON_MESSAGE = """
A CI skeleton has been generated! Please use the following steps
to complete the CI setup process:

1. Fill out {args.recipe_directory}/meta.yaml with your install and test code
2. Commit all changes to the repo.

        $ git add . && git commit -m "ran conda smithy skeleton"

3. Remember to register your repo with the CI providers.
4. Rerender this repo to generate the CI configurations files.
   This can be done with:

        $ conda smithy rerender -c auto

At any time in the future, you will be able to automatically update your CI configuration by
re-running the rerender command above. Happy testing!
"""


class CISkeleton(Subcommand):
    subcommand = "ci-skeleton"

    def __init__(self, parser):
        super(CISkeleton, self).__init__(
            parser, "Generate skeleton for using CI outside of a feedstock"
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--feedstock-directory",
            default=os.getcwd(),
            help="The directory of the feedstock git repository.",
            dest="feedstock_directory",
        )
        scp.add_argument(
            "-r",
            "--recipe-directory",
            default="recipe",
            dest="recipe_directory",
        )
        scp.add_argument("package_name", nargs="?")

    def __call__(self, args):
        from conda_smithy.ci_skeleton import generate

        # complete configuration
        if getattr(args, "package_name") is None:
            args.package_name = "package"

        generate(
            package_name=args.package_name,
            feedstock_directory=args.feedstock_directory,
            recipe_directory=args.recipe_directory,
        )
        print(POST_SKELETON_MESSAGE.format(args=args).strip())


class UpdateCB3(Subcommand):
    subcommand = "update-cb3"

    def __init__(self, parser):
        # conda-smithy update-cb3 ./
        super(UpdateCB3, self).__init__(
            parser, "Update a feedstock for conda-build=3"
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--recipe_directory",
            default=os.path.join(os.getcwd(), "recipe"),
            help="The path to the source recipe directory.",
        )
        scp.add_argument(
            "--output",
            default=None,
            help="Filename for the output. No output edits the recipe inplace",
        )
        scp.add_argument(
            "--cbc",
            default=None,
            help="Path to conda_build_config.yaml. No path will use conda-forge-pinning",
        )

    def __call__(self, args):
        from conda_smithy.update_cb3 import update_cb3
        from conda_smithy.configure_feedstock import get_cfp_file_path

        recipe_file = os.path.join(args.recipe_directory, "meta.yaml")
        output_file = args.output
        if output_file is None:
            output_file = recipe_file
        if args.cbc is None:
            cbc, _ = get_cfp_file_path()
        else:
            cbc = os.path.join(os.getcwd(), args.cbc)
        output_content, messages = update_cb3(recipe_file, cbc)
        with io.open(output_file, "w") as fh:
            fh.write(output_content)
        print("List of changes done to the recipe:")
        print(messages)


def main():

    parser = argparse.ArgumentParser(
        prog="conda smithy",
        description="a tool to help create, administer and manage feedstocks.",
    )
    subparser = parser.add_subparsers()
    # TODO: Consider allowing plugins/extensions using entry_points.
    # https://reinout.vanrees.org/weblog/2010/01/06/zest-releaser-entry-points.html
    for subcommand in Subcommand.__subclasses__():
        subcommand(subparser)
    # And the alias for rerender
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="Show conda-smithy's version, and exit.",
    )

    if not sys.argv[1:]:
        args = parser.parse_args(["--help"])
    else:
        args = parser.parse_args()

    # Check conda version for compatibility
    CONDA_VERSION_MAX = "5.0"
    if LooseVersion(conda.__version__) >= LooseVersion(CONDA_VERSION_MAX):
        print(
            "You appear to be using conda {}, but conda-smithy {}\n"
            "is currently only compatible with conda versions < {}.\n".format(
                conda.__version__, __version__, CONDA_VERSION_MAX
            )
        )
        sys.exit(2)

    args.subcommand_func(args)


class GenerateFeedstockToken(Subcommand):
    subcommand = "generate-feedstock-token"

    def __init__(self, parser):
        super(GenerateFeedstockToken, self).__init__(
            parser,
            "Generate a feedstock token at ~/.conda-smithy/{user or org}_{project}.token",
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--feedstock_directory",
            default=os.getcwd(),
            help="The directory of the feedstock git repository.",
        )
        group = scp.add_mutually_exclusive_group()
        group.add_argument(
            "--user", help="github username under which to register this repo"
        )
        group.add_argument(
            "--organization",
            default="conda-forge",
            help="github organisation under which to register this repo",
        )

    def __call__(self, args):
        from conda_smithy.feedstock_tokens import (
            generate_and_write_feedstock_token,
        )

        owner = args.user or args.organization
        repo = os.path.basename(os.path.abspath(args.feedstock_directory))

        generate_and_write_feedstock_token(owner, repo)
        print(
            "Your feedstock token has been generated at ~/.conda-smithy/%s_%s.token\n"
            "This token is stored in plaintext so be careful!" % (owner, repo)
        )


class RegisterFeedstockToken(Subcommand):
    subcommand = "register-feedstock-token"

    def __init__(self, parser):
        # conda-smithy register-ci ./
        super(RegisterFeedstockToken, self).__init__(
            parser,
            "Register the feedstock token w/ the CI services for builds and "
            "with the token registry. \n\n"
            "All exceptions are swallowed and stdout/stderr from this function is"
            "redirected to `/dev/null`. Sanitized error messages are"
            "displayed at the end.\n\n"
            "If you need to debug this function, define `DEBUG_ANACONDA_TOKENS` in"
            "your environment before calling this function.",
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--feedstock_directory",
            default=os.getcwd(),
            help="The directory of the feedstock git repository.",
        )
        scp.add_argument(
            "--token_repo",
            default=None,
            help=(
                "The GitHub repo that stores feedstock tokens. The default is "
                "{user or org}/feedstock-tokens on GitHub."
            ),
        )
        group = scp.add_mutually_exclusive_group()
        group.add_argument(
            "--user", help="github username under which to register this repo"
        )
        group.add_argument(
            "--organization",
            default="conda-forge",
            help="github organisation under which to register this repo",
        )
        for ci in [
            "Azure",
            "Travis",
            "Circle",
            "Drone",
        ]:
            scp.add_argument(
                "--without-{}".format(ci.lower()),
                dest=ci.lower(),
                action="store_false",
                help="If set, {} will be not registered".format(ci),
            )
            default = {ci.lower(): True}
            scp.set_defaults(**default)

    def __call__(self, args):
        from conda_smithy.feedstock_tokens import (
            register_feedstock_token_with_proviers,
            register_feedstock_token,
            feedstock_token_exists,
        )

        owner = args.user or args.organization
        repo = os.path.basename(os.path.abspath(args.feedstock_directory))

        if args.token_repo is None:
            token_repo = (
                "https://${GITHUB_TOKEN}@github.com/%s/feedstock-tokens"
                % owner
            )
        else:
            token_repo = args.token_repo

        if feedstock_token_exists(owner, repo, token_repo):
            raise RuntimeError(
                "Token for repo %s/%s already exists!" % (owner, repo)
            )

        print("Registering the feedstock tokens. Can take up to ~30 seconds.")

        # do all providers first
        register_feedstock_token_with_proviers(
            owner,
            repo,
            drone=args.drone,
            circle=args.circle,
            travis=args.travis,
            azure=args.azure,
        )

        # then if that works do the github repo
        register_feedstock_token(owner, repo, token_repo)

        print("Successfully registered the feedstock token!")


class UpdateAnacondaToken(Subcommand):
    subcommand = "update-anaconda-token"
    aliases = [
        "rotate-anaconda-token",
        "update-binstar-token",
        "rotate-binstar-token",
    ]

    def __init__(self, parser):
        super(UpdateAnacondaToken, self).__init__(
            parser,
            "Update the anaconda/binstar token used for package uploads.\n\n"
            "All exceptions are swallowed and stdout/stderr from this function is"
            "redirected to `/dev/null`. Sanitized error messages are"
            "displayed at the end.\n\n"
            "If you need to debug this function, define `DEBUG_ANACONDA_TOKENS` in"
            "your environment before calling this function.",
        )
        scp = self.subcommand_parser
        scp.add_argument(
            "--feedstock_directory",
            default=os.getcwd(),
            help="The directory of the feedstock git repository.",
        )
        scp.add_argument(
            "--token_name",
            default="BINSTAR_TOKEN",
            help="The name of the environment variable you'd like to hold the token.",
        )
        group = scp.add_mutually_exclusive_group()
        group.add_argument("--user", help="github username of the repo")
        group.add_argument(
            "--organization",
            default="conda-forge",
            help="github organization of the repo",
        )
        for ci in [
            "Azure",
            "Travis",
            "Circle",
            "Drone",
            "Appveyor",
        ]:
            scp.add_argument(
                "--without-{}".format(ci.lower()),
                dest=ci.lower(),
                action="store_false",
                help="If set, the token on {} will be not changed.".format(ci),
            )
            default = {ci.lower(): True}
            scp.set_defaults(**default)

    def __call__(self, args):
        from conda_smithy.anaconda_token_rotation import rotate_anaconda_token

        owner = args.user or args.organization
        repo = os.path.basename(os.path.abspath(args.feedstock_directory))

        print(
            "Updating the anaconda/binstar token. Can take up to ~30 seconds."
        )

        # do all providers first
        rotate_anaconda_token(
            owner,
            repo,
            args.feedstock_directory,
            drone=args.drone,
            circle=args.circle,
            travis=args.travis,
            azure=args.azure,
            appveyor=args.appveyor,
            token_name=args.token_name,
        )

        print("Successfully updated the anaconda/binstar token!")
        if args.appveyor:
            print(
                "Appveyor tokens are stored in the repo so you must commit the "
                "local changes and push them before the new token will be used!"
            )


if __name__ == "__main__":
    main()
