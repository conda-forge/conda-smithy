"""This module updates/rotates anaconda/binstar tokens.

The correct way to use this module is to call its functions via the command
line utility. The relevant one is

    conda-smithy update-anaconda-token
"""

import os
import sys
from contextlib import redirect_stderr, redirect_stdout

from github import Github


def _get_anaconda_token():
    """use this helper to enable easier patching for tests"""
    try:
        from conda_smithy.ci_register import anaconda_token

        return anaconda_token
    except ImportError:
        raise RuntimeError(
            "You must have the anaconda token defined to do token rotation!"
        )


def rotate_anaconda_token(
    user,
    project,
    feedstock_config_path,
    azure=True,
    github_actions=True,
    token_name="BINSTAR_TOKEN",
):
    """Rotate the anaconda (binstar) token used by the CI providers

    All exceptions are swallowed and stdout/stderr from this function is
    redirected to `/dev/null`. Sanitized error messages are
    displayed at the end.

    If you need to debug this function, define `DEBUG_ANACONDA_TOKENS` in
    your environment before calling this function.
    """
    # we are swallong all of the logs below, so we do a test import here
    # to generate the proper errors for missing tokens
    # note that these imports cover all providers
    from .azure_ci_utils import default_config  # noqa
    from conda_smithy.github import gh_token

    anaconda_token = _get_anaconda_token()

    # capture stdout, stderr and suppress all exceptions so we don't
    # spill tokens
    failed = False
    err_msg = None
    with open(os.devnull, "w") as fp:
        if "DEBUG_ANACONDA_TOKENS" in os.environ:
            fpo = sys.stdout
            fpe = sys.stderr
        else:
            fpo = fp
            fpe = fp

        with redirect_stdout(fpo), redirect_stderr(fpe):
            try:
                if azure:
                    try:
                        rotate_token_in_azure(user, project, anaconda_token, token_name)
                    except Exception as e:
                        if "DEBUG_ANACONDA_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                f"Failed to rotate token for {user}/{project} on azure!"
                            )
                            failed = True
                            raise RuntimeError(err_msg)

                if github_actions:
                    gh = Github(gh_token())
                    try:
                        rotate_token_in_github_actions(
                            user, project, anaconda_token, token_name, gh
                        )
                    except Exception as e:
                        if "DEBUG_ANACONDA_TOKENS" in os.environ:
                            raise e
                        else:
                            err_msg = (
                                f"Failed to rotate token for {user}/{project}"
                                " on github actions!"
                            )
                            failed = True
                            raise RuntimeError(err_msg)

            except Exception as e:
                if "DEBUG_ANACONDA_TOKENS" in os.environ:
                    raise e
                failed = True

    if failed:
        if err_msg:
            raise RuntimeError(err_msg)
        else:
            raise RuntimeError(
                f"Rotating the feedstock token in providers for {user}/{project} failed!"
                " Try the command locally with DEBUG_ANACONDA_TOKENS"
                " defined in the environment to investigate!"
            )


def rotate_token_in_azure(user, project, binstar_token, token_name):
    from vsts.build.v4_1.models import BuildDefinitionVariable

    from conda_smithy.azure_ci_utils import (
        build_client,
        get_default_build_definition,
    )
    from conda_smithy.azure_ci_utils import default_config as config

    bclient = build_client()

    existing_definitions = bclient.get_definitions(
        project=config.project_name, name=project
    )
    if existing_definitions:
        assert len(existing_definitions) == 1
        ed = existing_definitions[0]
    else:
        raise RuntimeError(
            f"Cannot add {token_name} to a repo that is not already registerd on azure CI!"
        )

    ed = bclient.get_definition(ed.id, project=config.project_name)

    if not hasattr(ed, "variables") or ed.variables is None:
        variables = {}
    else:
        variables = ed.variables

    variables[token_name] = BuildDefinitionVariable(
        allow_override=False,
        is_secret=True,
        value=binstar_token,
    )

    build_definition = get_default_build_definition(
        user,
        project,
        config=config,
        variables=variables,
        id=ed.id,
        revision=ed.revision,
    )

    bclient.update_definition(
        definition=build_definition,
        definition_id=ed.id,
        project=ed.project.name,
    )


def rotate_token_in_github_actions(user, project, binstar_token, token_name, gh):
    repo = gh.get_repo(f"{user}/{project}")
    assert repo.create_secret(token_name, binstar_token)
