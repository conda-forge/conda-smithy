import os
from random import choice

import github
from git import Repo
from github import Github
from github.GithubException import GithubException
from github.Organization import Organization
from github.Team import Team

from conda_smithy.configure_feedstock import (
    _load_forge_config,
    get_cached_cfp_file_path,
)
from conda_smithy.utils import (
    _get_metadata_from_feedstock_dir,
    get_feedstock_name_from_meta,
)


def gh_token():
    try:
        with open(os.path.expanduser("~/.conda-smithy/github.token")) as fh:
            token = fh.read().strip()
        if not token:
            raise ValueError()
    except (OSError, ValueError):
        msg = (
            "No github token. Go to https://github.com/settings/tokens/new and generate\n"
            "a token with repo access. Put it in ~/.conda-smithy/github.token"
        )
        raise RuntimeError(msg)
    return token


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
    cached_file = os.path.expanduser(
        f"~/.conda-smithy/{org.login}-{team_name}-team"
    )
    try:
        with open(cached_file) as fh:
            team_id = int(fh.read().strip())
            return org.get_team(team_id)
    except OSError:
        pass

    try:
        repo = org.get_repo(f"{team_name}-feedstock")
        team = next(
            (team for team in repo.get_teams() if team.name == team_name), None
        )
        if team:
            return team
    except GithubException:
        pass

    team = next(
        (team for team in org.get_teams() if team.name == team_name), None
    )
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
    _, ruleset_list = gh_repo._requester.requestJsonAndCheck(
        "GET", rulesets_url
    )
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
            "conditions": {
                "ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}
            },
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

    gh = Github(token)
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
    repo = Repo(args.feedstock_directory)
    remote_name = args.remote_name.strip()
    if remote_name:
        if remote_name in [remote.name for remote in repo.remotes]:
            existing_remote = repo.remotes[remote_name]
            if existing_remote.url != gh_repo.ssh_url:
                print(
                    f"Remote {remote_name} already exists, and doesn't point to {gh_repo.ssh_url} "
                    f"(it points to {existing_remote.url})."
                )
        else:
            repo.create_remote(remote_name, gh_repo.ssh_url)

    if args.extra_admin_users is not None:
        for user in args.extra_admin_users:
            gh_repo.add_to_collaborators(user, "admin")

    if args.add_teams:
        if isinstance(user_or_org, Organization):
            configure_github_team(
                metadata, gh_repo, user_or_org, feedstock_name
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


def configure_github_team(meta, gh_repo, org, feedstock_name, remove=True):
    # Add a team for this repo and add the maintainers to it.
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

    maintainers = set(meta.meta.get("extra", {}).get("recipe-maintainers", []))
    maintainers = set(maintainer.lower() for maintainer in maintainers)
    maintainer_teams = set(m for m in maintainers if "/" in m)
    maintainers = set(m for m in maintainers if "/" not in m)

    # Try to get team or create it if it doesn't exist.
    team_name = feedstock_name
    current_maintainer_teams = list(gh_repo.get_teams())
    fs_team = next(
        (team for team in current_maintainer_teams if team.name == team_name),
        None,
    )
    current_maintainers = set()
    if not fs_team:
        fs_team = create_team(
            org,
            team_name,
            f"The {choice(superlative)} {team_name} contributors!",
        )
        fs_team.add_to_repos(gh_repo)

    current_maintainers = set([e.login.lower() for e in fs_team.get_members()])

    # Get the all-members team
    description = f"All of the awesome {org.login} contributors!"
    all_members_team = get_cached_team(org, "all-members", description)
    new_org_members = set()

    # Add only the new maintainers to the team.
    # Also add the new maintainers to all-members if not already included.
    for new_maintainer in maintainers - current_maintainers:
        add_membership(fs_team, new_maintainer)

        if not has_in_members(all_members_team, new_maintainer):
            add_membership(all_members_team, new_maintainer)
            new_org_members.add(new_maintainer)

    # Remove any maintainers that need to be removed (unlikely here).
    if remove:
        for old_maintainer in current_maintainers - maintainers:
            remove_membership(fs_team, old_maintainer)

    # Add any new maintainer teams
    maintainer_teams = set(
        m.split("/")[1]
        for m in maintainer_teams
        if m.startswith(str(org.login))
    )
    current_maintainer_team_objs = {
        team.slug: team for team in current_maintainer_teams
    }
    current_maintainer_teams = set(
        [team.slug for team in current_maintainer_teams]
    )
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

    return maintainers, current_maintainers, new_org_members
