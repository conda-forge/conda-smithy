import base64
import copy
import json
import logging
import os
from random import choice

import github
import pygit2
from github import Github
from github.Consts import DEFAULT_BASE_URL as GITHUB_API_URL
from github.GithubException import GithubException
from github.Organization import Organization
from github.Team import Team

from conda_smithy.configure_feedstock import (
    _load_forge_config,
    get_cached_cfp_file_path,
)
from conda_smithy.utils import (
    _get_metadata_from_feedstock_dir,
    file_permissions,
    get_feedstock_name_from_meta,
)

logger = logging.getLogger(__name__)


def gh_token():
    try:
        github_token_path = os.path.expanduser("~/.conda-smithy/github.token")
        if file_permissions(github_token_path) != "0o600":
            raise ValueError("Incorrect permissions")
        with open(github_token_path) as fh:
            token = fh.read().strip()
        if not token:
            raise ValueError()
    except (OSError, ValueError):
        msg = (
            "No github token. Go to https://github.com/settings/tokens/new and generate\n"
            "a token with repo access. Put it in ~/.conda-smithy/github.token with chmod 600"
        )
        raise RuntimeError(msg)
    return token


def github_client(token: str | None = None) -> github.Github:
    return Github(auth=github.Auth.Token(token or gh_token()))


def _test_and_raise_besides_file_not_exists(e: github.GithubException):
    if isinstance(e, github.UnknownObjectException):
        return
    if e.status == 404 and "No object found" in e.data["message"]:
        return
    raise e


def _get_path_blob_sha_and_content(
    path: str, repo: github.Repository.Repository
) -> tuple[str | None, str | None]:
    try:
        cnt = repo.get_contents(path)
        # I was using the decoded_content attribute here, but it seems that
        # every once and a while github does not send the encoding correctly
        # so I switched to doing the decoding by hand.
        data = base64.b64decode(cnt.content.encode("utf-8")).decode("utf-8")
        return cnt.sha, data
    except github.GithubException as e:
        _test_and_raise_besides_file_not_exists(e)
        return None, None


def pull_file_via_gh_api(repo: github.Repository.Repository, pth: str) -> str | None:
    """Pull a file from a repo via the GitHub API.

    Parameters
    ----------
    repo
        The repo as a pygithub object.
    pth
        The path to the file.

    Returns
    -------
    data
        The file contents as a string. Returns `None` if file does not exist.
    """
    _, cnt = _get_path_blob_sha_and_content(pth, repo)
    return cnt


def push_file_via_gh_api(
    repo: github.Repository.Repository, pth: str, data: str, msg: str
) -> None:
    """Push a file to a repo via the GitHub API.

    Parameters
    ----------
    repo
        The repo as a pygithub object.
    pth
        The path of the file in the repo.
    data
        The file data as a utf-8 string.
    msg
        The commit message.
    """
    sha, cnt = _get_path_blob_sha_and_content(pth, repo)
    if sha is None:
        repo.create_file(pth, msg, data)
    else:
        if cnt != data:
            repo.update_file(pth, msg, data, sha)


def create_team(org, name, description, repo_names=[]):
    # PyGithub creates secret teams, and has no way of turning that off! :(
    post_parameters = {
        "name": name,
        "description": description,
        "privacy": "closed",
        "permission": "push",
        "repo_names": repo_names,
    }
    headers, data = org._requester.requestJsonAndCheck(
        "POST", org.url + "/teams", input=post_parameters
    )
    return Team(org._requester, headers, data, completed=True)


def add_membership(team, member):
    headers, data = team._requester.requestJsonAndCheck(
        "PUT", team.url + "/memberships/" + member
    )
    return (headers, data)


def remove_membership(team, member):
    headers, data = team._requester.requestJsonAndCheck(
        "DELETE", team.url + "/memberships/" + member
    )
    return (headers, data)


def has_in_members(team, member):
    status, headers, data = team._requester.requestJson(
        "GET", team.url + "/members/" + member
    )
    return status == 204


def get_cached_team(org, team_name, description=""):
    cached_file = os.path.expanduser(f"~/.conda-smithy/{org.login}-{team_name}-team")
    try:
        with open(cached_file) as fh:
            team_id = int(fh.read().strip())
            return org.get_team(team_id)
    except OSError:
        pass

    try:
        repo = org.get_repo(f"{team_name}-feedstock")
        team = next((team for team in repo.get_teams() if team.name == team_name), None)
        if team:
            return team
    except GithubException:
        pass

    team = next((team for team in org.get_teams() if team.name == team_name), None)
    if not team:
        if description:
            team = create_team(org, team_name, description, [])
        else:
            raise RuntimeError(f"Couldn't find team {team_name}")

    with open(cached_file, "w") as fh:
        fh.write(str(team.id))

    return team


def _conda_forge_specific_repo_setup(gh_repo):
    # setup branch protections ruleset
    # default branch may not exist yet
    ruleset_name = "conda-forge-branch-protection"

    # first, check if the ruleset exists already
    rulesets_url = gh_repo.url + "/rulesets"
    _, ruleset_list = gh_repo._requester.requestJsonAndCheck("GET", rulesets_url)
    ruleset_id = None
    for ruleset in ruleset_list:
        if ruleset["name"] == ruleset_name:
            ruleset_id = ruleset["id"]
            break

    if ruleset_id is not None:
        print("Updating branch protections")
        # update ruleset
        method = "PUT"
        url = f"{rulesets_url}/{ruleset_id}"
    else:
        print("Enabling branch protections")
        # new ruleset
        method = "POST"
        url = rulesets_url

    gh_repo._requester.requestJsonAndCheck(
        method,
        url,
        input={
            "name": ruleset_name,
            "target": "branch",
            "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
            "enforcement": "active",
        },
    )


def create_github_repo(args):
    token = gh_token()

    # Load the conda-forge config and read metadata from the feedstock recipe
    forge_config = _load_forge_config(args.feedstock_directory, None)
    metadata = _get_metadata_from_feedstock_dir(
        args.feedstock_directory,
        forge_config,
        conda_forge_pinning_file=(
            get_cached_cfp_file_path(".")[0]
            if args.user is None and args.organization == "conda-forge"
            else None
        ),
    )

    feedstock_name = get_feedstock_name_from_meta(metadata)

    gh = github_client(token=token)
    user_or_org = None
    is_conda_forge = False
    if args.user is not None:
        pass
        # User has been defined, and organization has not.
        user_or_org = gh.get_user()
    else:
        # Use the organization provided.
        user_or_org = gh.get_organization(args.organization)
        if args.organization == "conda-forge":
            is_conda_forge = True

    repo_name = f"{feedstock_name}-feedstock"
    try:
        gh_repo = user_or_org.create_repo(
            repo_name,
            has_wiki=False,
            private=args.private,
            description=f"A conda-smithy repository for {feedstock_name}.",
        )

        if is_conda_forge:
            _conda_forge_specific_repo_setup(gh_repo)

        print(f"Created {gh_repo.full_name} on github")
    except GithubException as gh_except:
        if (
            gh_except.data.get("errors", [{}])[0].get("message", "")
            != "name already exists on this account"
        ):
            raise
        gh_repo = user_or_org.get_repo(repo_name)
        print("Github repository already exists.")

    # Now add this new repo as a remote on the local clone.
    repo = pygit2.Repository(args.feedstock_directory)
    remote_name = args.remote_name.strip()
    if remote_name:
        if remote_name in repo.remotes.names():
            existing_remote = repo.remotes[remote_name]
            if existing_remote.url != gh_repo.ssh_url:
                print(
                    f"Remote {remote_name} already exists, and doesn't point to {gh_repo.ssh_url} "
                    f"(it points to {existing_remote.url})."
                )
        else:
            repo.remotes.create(remote_name, gh_repo.ssh_url)

    if args.extra_admin_users is not None:
        for user in args.extra_admin_users:
            gh_repo.add_to_collaborators(user, "admin")

    if args.add_teams:
        if isinstance(user_or_org, Organization):
            configure_github_team(
                metadata, gh_repo, user_or_org, feedstock_name, remove=True, gh=gh
            )


def accept_all_repository_invitations(gh):
    user = gh.get_user()
    invitations = github.PaginatedList.PaginatedList(
        github.Invitation.Invitation,
        user._requester,
        user.url + "/repository_invitations",
        None,
    )
    for invite in invitations:
        invite._requester.requestJsonAndCheck("PATCH", invite.url)


def remove_from_project(gh, org, project):
    user = gh.get_user()
    repo = gh.get_repo(f"{org}/{project}")
    repo.remove_from_collaborators(user.login)


def configure_github_team(
    meta, gh_repo, org, feedstock_name, remove=True, gh: Github | None = None
):
    """Add a team for this repo and add/remove the maintainers to it."""

    gh = gh or github_client()

    superlative = [
        "awesome",
        "slick",
        "formidable",
        "awe-inspiring",
        "breathtaking",
        "magnificent",
        "wonderous",
        "stunning",
        "astonishing",
        "superb",
        "splendid",
        "impressive",
        "unbeatable",
        "excellent",
        "top",
        "outstanding",
        "exalted",
        "standout",
        "smashing",
    ]

    # get maintainers in the recipe
    maintainers = set(meta.meta.get("extra", {}).get("recipe-maintainers", []))
    maintainers = {maintainer.lower() for maintainer in maintainers}
    maintainer_teams = {m for m in maintainers if "/" in m}
    maintainers = {m for m in maintainers if "/" not in m}

    # get current maintainer to durable ID mapping in feedstock
    recipe_maintainers_file = ".recipe_maintainers.json"
    curr_maintainer2id = json.loads(
        pull_file_via_gh_api(gh_repo, recipe_maintainers_file) or "{}"
    )
    new_maintainer2id = copy.deepcopy(curr_maintainer2id)

    # Try to get team or create it if it doesn't exist.
    team_name = feedstock_name
    current_maintainer_teams = list(gh_repo.get_teams())
    repo_fs_team = next(
        (team for team in current_maintainer_teams if team.name == team_name),
        None,
    )
    fs_team = None
    current_maintainers = set()

    if not repo_fs_team:
        team_desc = f"The {choice(superlative)} {team_name} contributors!"

        try:
            # first try to make it since a search of the org will be expensive
            fs_team = create_team(
                org,
                team_name,
                team_desc,
            )
        except Exception:
            # try a full search of the org or the local cache
            fs_team = get_cached_team(
                org,
                team_name,
                description=team_desc,
            )
    else:
        fs_team = repo_fs_team

    if fs_team is None:
        raise RuntimeError(
            f"Could not find feedstock team for feedstock {feedstock_name}!"
        )

    if not repo_fs_team:
        # team is not added to repo so do that
        fs_team.add_to_repos(gh_repo)

    current_maintainers = {e.login.lower() for e in fs_team.get_members()}

    # Get the all-members team
    description = f"All of the awesome {org.login} contributors!"
    all_members_team = get_cached_team(org, "all-members", description)
    new_org_members = set()

    # we cache this mapping once so that it consistently used throughout
    # the function
    cached_username2id = {}
    for uname in (current_maintainers - maintainers) | (
        maintainers - current_maintainers
    ):
        try:
            uid = gh.get_user(uname).id
        except Exception:
            uid = None
            logger.warning(
                "Could not get user ID for user '%s'! Their feedstock permissions will not be changed.",
                uname,
            )

        cached_username2id[uname] = uid

    # some notes - MRB
    # The definitions of the variables is as follows
    #
    #  - maintainers: the set of usernames listed in the recipe/meta.yaml
    #  - current_maintainers: the set of usernames corresponding to the people
    #    who are a part of the github feedstock team
    #  - new_maintainer: a username in the recipe/meta.yaml, but not in the set
    #    of usernames corresponding to the unique people on the github feedstock
    #    team.
    #
    # The correct set of usernames that should be in the github feedstock team are
    # the usernames that both:
    #
    #  - appear in the recipe/meta.yaml
    #  - map to the same unique userid as it was recorded in the curr_maintainer2id
    #    mapping
    #
    # The code below goes through each new_maintainer (i.e. a username that is in the
    # recipe/meta.yaml, but not in the github team), and checks that it maps
    # to the correct userid as previously recorded in curr_maintainer2id (if one was).
    # If it finds a mismatch, the username must have
    # been mapped to a new userid and thus we do NOT add this person to the github team.
    # If the username is not found in the mapping, we add it to the mapping and add the
    # person to the team.
    # We do not need to check the ID condition for the users in current_maintainers
    # since github ensures that username changes do not escalate permissions itself.

    # Add only the new maintainers to the team.
    # Also add the new maintainers to all-members if not already included.
    for new_maintainer in maintainers - current_maintainers:
        # if we could not fetch the ID for a user, then skip doing anything
        if cached_username2id[new_maintainer] is None:
            continue

        # if a new maintainer is in the current mapping of logins to IDs and the ID
        # does not match, then we do not add them to the repo or conda-forge.
        # MRB: I am not relying on `.get` with a default to None here to ensure that if we happen
        # to somehow write an entry with the ID as null in json, we do not add users.
        if new_maintainer in curr_maintainer2id:
            new_maintainer_id = cached_username2id[new_maintainer]
            if curr_maintainer2id[new_maintainer] != new_maintainer_id:
                logger.warning(
                    "Did not add user '%s' since new id '%s' does not match current id '%s'!",
                    new_maintainer,
                    new_maintainer_id,
                    curr_maintainer2id[new_maintainer],
                )
                continue

        add_membership(fs_team, new_maintainer)

        if not has_in_members(all_members_team, new_maintainer):
            add_membership(all_members_team, new_maintainer)
            new_org_members.add(new_maintainer)

        # if we have not recorded the new maintainer's ID yet, we do that now
        if new_maintainer not in new_maintainer2id:
            new_maintainer2id[new_maintainer] = gh.get_user(new_maintainer).id

    # Remove any maintainers that need to be removed (unlikely here).
    if remove:
        for old_maintainer in current_maintainers - maintainers:
            # FIXME: skipping this check for now. The issue is that we
            # cannot distinguish between maintainers on the team
            # currently who want to be removed (and have also changed
            # their username) vs the same situation where a person does
            # not want to be removed. The solution is to either update
            # the recipe with the username change or have the maintainer
            # who wants to be removed from the feedstock delete their
            # entry in the ID registry in addition to removing their
            # old username from the recipe. Instead of either of those,
            # for now we simply remove everyone. This matches
            # the current conda-forge default behavior anyways
            # so is fine. - MRB
            # COMMENTED CODE
            # # if we could not fetch the ID for a user, then skip doing anything
            # if cached_username2id[old_maintainer] is None:
            #     continue

            # # we do not remove maintainers whose ID is in the registry
            # # but username has changed. These are legit members who have
            # # changed their usernames.
            # old_maintainer_id = cached_username2id[old_maintainer]
            # skip_remove = False
            # for username, userid in curr_maintainer2id.items():
            #     if username != old_maintainer and userid == old_maintainer_id:
            #         skip_remove = True
            # if skip_remove:
            #     continue
            # END OF COMMENTED CODE

            # we get to here only if a maintainer being removed has the
            # same username and ID as it was recorded in the registry
            # and they are no longer in the list in the recipe
            remove_membership(fs_team, old_maintainer)

            # if someone leaves, we remove their ID.
            # that way if the username gets mapped to a new ID later,
            # we can add that new person.
            # MRB: this removal is safe since this username is no longer
            # in the recipe/meta.yaml
            new_maintainer2id.pop(old_maintainer, None)

    # Add any new maintainer teams
    maintainer_teams = {
        m.split("/")[1] for m in maintainer_teams if m.startswith(str(org.login))
    }
    current_maintainer_team_objs = {
        team.slug: team for team in current_maintainer_teams
    }
    current_maintainer_teams = {team.slug for team in current_maintainer_teams}
    for new_team in maintainer_teams - current_maintainer_teams:
        team = org.get_team_by_slug(new_team)
        team.add_to_repos(gh_repo)

    # remove any old teams
    if remove:
        for old_team in current_maintainer_teams - maintainer_teams:
            team = current_maintainer_team_objs.get(
                old_team, org.get_team_by_slug(old_team)
            )
            if team.name == fs_team.name:
                continue
            team.remove_from_repos(gh_repo)

    # finally we push the maintainer to ID mapping if it is changed
    if new_maintainer2id != curr_maintainer2id:
        changed_folks = sorted(set(new_maintainer2id) - set(curr_maintainer2id))
        push_file_via_gh_api(
            gh_repo,
            recipe_maintainers_file,
            json.dumps(new_maintainer2id, sort_keys=True, indent=2),
            f"[ci skip] [skip ci] [cf admin skip] ***NO_CI*** add/remove IDs for maintainers {changed_folks!r}",
        )

    return maintainers, current_maintainers, new_org_members


def configure_github_app(
    org: str,
    repo: str,
    app_slug_or_installation_id: str | int = None,
    remove: bool = False,
) -> None:
    gh = github_client()
    org: github.Organization = gh.get_organization(org)
    repo: github.Repository = org.get_repo(repo)
    inst_id: int = 0
    if isinstance(app_slug_or_installation_id, str):
        for inst in org.get_installations():
            if inst.app_slug == app_slug_or_installation_id:
                inst_id = inst.id
                break
        else:
            raise ValueError(
                f"Could not find installation ID for '{app_slug_or_installation_id}'. "
                "Is it installed?"
            )
    else:
        inst_id = app_slug_or_installation_id
    url = f"{GITHUB_API_URL}/user/installations/{inst_id}/repositories/{repo.id}"
    if remove:
        gh.requester.requestJsonAndCheck("DELETE", url)
    else:
        gh.requester.requestJsonAndCheck("PUT", url)
