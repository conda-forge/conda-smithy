import os
from random import choice

from git import Repo

from github import Github
from github.GithubException import GithubException
from github.Organization import Organization
from github.Team import Team
import github

import conda_build.api


def gh_token():
    try:
        with open(os.path.expanduser("~/.conda-smithy/github.token"), "r") as fh:
            token = fh.read().strip()
        if not token:
            raise ValueError()
    except (IOError, ValueError):
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
        "~/.conda-smithy/{}-{}-team".format(org.login, team_name)
    )
    try:
        with open(cached_file, "r") as fh:
            team_id = int(fh.read().strip())
            return org.get_team(team_id)
    except IOError:
        pass

    try:
        repo = org.get_repo("{}-feedstock".format(team_name))
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
            raise RuntimeError("Couldn't find team {}".format(team_name))

    with open(cached_file, "w") as fh:
        fh.write(str(team.id))

    return team


def create_github_repo(args):
    token = gh_token()
    meta = conda_build.api.render(
        args.feedstock_directory,
        permit_undefined_jinja=True,
        finalize=False,
        bypass_env_check=True,
        trim_skip=False,
    )[0][0]

    if "parent_recipe" in meta.meta["extra"]:
        feedstock_name = meta.meta["extra"]["parent_recipe"]["name"]
    else:
        feedstock_name = meta.name()

    gh = Github(token)
    user_or_org = None
    if args.user is not None:
        pass
        # User has been defined, and organization has not.
        user_or_org = gh.get_user()
    else:
        # Use the organization provided.
        user_or_org = gh.get_organization(args.organization)

    repo_name = "{}-feedstock".format(feedstock_name)
    try:
        gh_repo = user_or_org.create_repo(
            repo_name,
            has_wiki=False,
            description="A conda-smithy repository for {}.".format(feedstock_name),
        )
        print("Created {} on github".format(gh_repo.full_name))
    except GithubException as gh_except:
        if (
            gh_except.data.get("errors", [{}])[0].get("message", "")
            != u"name already exists on this account"
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
                    "Remote {} already exists, and doesn't point to {} "
                    "(it points to {}).".format(
                        remote_name, gh_repo.ssh_url, existing_remote.url
                    )
                )
        else:
            repo.create_remote(remote_name, gh_repo.ssh_url)

    if args.extra_admin_users is not None:
        for user in args.extra_admin_users:
            gh_repo.add_to_collaborators(user, "admin")

    if args.add_teams:
        if isinstance(user_or_org, Organization):
            configure_github_team(meta, gh_repo, user_or_org, feedstock_name)


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
    repo = gh.get_repo("{}/{}".format(org, project))
    repo.remove_from_collaborators(user.login)


def configure_github_team(meta, gh_repo, org, feedstock_name):

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
    team = next(
        (team for team in current_maintainer_teams if team.name == team_name), None
    )
    current_maintainers = set()
    if not team:
        team = create_team(
            org,
            team_name,
            "The {} {} contributors!".format(choice(superlative), team_name),
        )
        team.add_to_repos(gh_repo)
    else:
        current_maintainers = set([e.login.lower() for e in team.get_members()])

    # Get the all-members team
    description = "All of the awesome {} contributors!".format(org.login)
    all_members_team = get_cached_team(org, "all-members", description)
    new_org_members = set()

    # Add only the new maintainers to the team.
    # Also add the new maintainers to all-members if not already included.
    for new_maintainer in maintainers - current_maintainers:
        add_membership(team, new_maintainer)

        if not has_in_members(all_members_team, new_maintainer):
            print(
                "Adding a new member ({}) to {}. Welcome! :)".format(
                    new_maintainer, org.login
                )
            )
            add_membership(all_members_team, new_maintainer)
            new_org_members.add(new_maintainer)

    # Mention any maintainers that need to be removed (unlikely here).
    for old_maintainer in current_maintainers - maintainers:
        print(
            "AN OLD MEMBER ({}) NEEDS TO BE REMOVED FROM {}".format(
                old_maintainer, gh_repo
            )
        )

    # Add any new maintainer team
    maintainer_teams = set(
        m.split("/")[1] for m in maintainer_teams if m.startswith(str(org.login))
    )
    current_maintainer_teams = [team.name for team in current_maintainer_teams]
    for maintainer_team in maintainer_teams - set(current_maintainer_teams):
        print(
            "Adding a new team ({}) to {}. Welcome! :)".format(
                maintainer_team, org.login
            )
        )

        team = get_cached_team(org, maintainer_team)
        team.add_to_repos(gh_repo)

    return maintainers, current_maintainers, new_org_members
