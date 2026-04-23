import json
import unittest.mock as mock

import github
import pytest

from conda_smithy.github import _guess_team_slug, configure_github_team


@pytest.mark.parametrize(
    "team,slug",
    [
        (" - - - blah@$!#$!$- ", "blah"),
        ("-R.nmf five", "r-nmf-five"),
    ],
)
def test_guess_team_slug(team, slug):
    assert _guess_team_slug(team) == slug


@mock.patch("conda_smithy.github.has_in_members")
@mock.patch("conda_smithy.github.remove_membership")
@mock.patch("conda_smithy.github.add_membership")
@mock.patch("conda_smithy.github.get_cached_team")
@mock.patch("conda_smithy.github.create_team")
@mock.patch("conda_smithy.github.push_file_via_gh_api")
@mock.patch("conda_smithy.github.pull_file_via_gh_api")
def test_github_configure_github_team_all_new(
    gh_file_pull,
    gh_file_push,
    create_team,
    get_cached_team,
    add_membership,
    remove_membership,
    has_in_members,
):

    def gh_get_user_return(name):
        mck = mock.MagicMock()
        mck.id = int(name.replace("user", ""))
        return mck

    team = mock.MagicMock()
    team.slug = "team"

    def get_team_by_slug_return(_team):
        if _team == "pkg1":
            raise ValueError("Team does not exist!")
        elif _team == "team":
            return team
        else:
            assert False, "get_team_by_slug called with wrong team " + _team + "!"

    meta = mock.MagicMock()
    meta.meta = {"extra": {"recipe-maintainers": ["user1", "user2", "org-name/team"]}}

    gh_repo = mock.MagicMock(spec=github.Repository.Repository)
    gh_repo.get_teams.return_value = []

    org = mock.MagicMock(spec=github.Organization.Organization)
    org.login = "org-name"
    org.get_team_by_slug.side_effect = get_team_by_slug_return
    feedstock_name = "pkg1"  # without '-feedstock'

    gh = mock.MagicMock(spec=github.Github)
    gh_file_pull.return_value = None
    gh.get_user.side_effect = gh_get_user_return

    has_in_members.return_value = False

    configure_github_team(meta, gh_repo, org, feedstock_name, remove=True, gh=gh)

    gh_file_pull.assert_called_once_with(gh_repo, ".recipe_maintainers.json")
    gh_repo.get_teams.assert_called_once_with()
    org.get_team_by_slug.assert_has_calls(
        [
            mock.call("pkg1"),
            mock.call("team"),
        ],
        any_order=True,
    )
    create_team.assert_called_once()  # did not patch random.choice so do not assert actual call
    create_team.return_value.add_to_repos.assert_called_once_with(gh_repo)
    create_team.return_value.get_members.assert_called_once_with()
    get_cached_team.assert_called_once()  # do not bother to check call here
    add_membership.assert_has_calls(
        [
            mock.call(create_team.return_value, "user1"),
            mock.call(create_team.return_value, "user2"),
        ],
        any_order=True,
    )
    has_in_members.assert_has_calls(
        [
            mock.call(get_cached_team.return_value, "user1"),
            mock.call(get_cached_team.return_value, "user2"),
        ],
        any_order=True,
    )
    add_membership.assert_has_calls(
        [
            mock.call(get_cached_team.return_value, "user1"),
            mock.call(get_cached_team.return_value, "user2"),
        ],
        any_order=True,
    )
    remove_membership.assert_not_called()
    team.add_to_repos.assert_called_with(gh_repo)
    org.get_team_by_slug.return_value.remove_from_repos.assert_not_called()

    gh_file_push.assert_called_once_with(
        gh_repo,
        ".recipe_maintainers.json",
        json.dumps({"user1": 1, "user2": 2}, sort_keys=True, indent=2),
        "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** add/remove IDs for maintainers ['user1', 'user2']",
    )


@mock.patch("conda_smithy.github.has_in_members")
@mock.patch("conda_smithy.github.remove_membership")
@mock.patch("conda_smithy.github.add_membership")
@mock.patch("conda_smithy.github.get_cached_team")
@mock.patch("conda_smithy.github.create_team")
@mock.patch("conda_smithy.github.push_file_via_gh_api")
@mock.patch("conda_smithy.github.pull_file_via_gh_api")
def test_github_configure_github_team_add(
    gh_file_pull,
    gh_file_push,
    create_team,
    get_cached_team,
    add_membership,
    remove_membership,
    has_in_members,
):

    def gh_get_user_return(name):
        mck = mock.MagicMock()
        mck.id = int(name.replace("user", ""))
        return mck

    team = mock.MagicMock()
    team.slug = "team"

    pkg1_team = mock.MagicMock()
    pkg1_team.slug = "pkg1"
    pkg1_team.name = "pkg1"
    user1 = mock.MagicMock()
    user1.login = "user1"
    user2 = mock.MagicMock()
    user2.login = "user2"
    pkg1_team.get_members.return_value = [
        user2,
        user1,
    ]

    new_team = mock.MagicMock()
    new_team.slug = "new-team"

    def get_team_by_slug_return(_team):
        if _team == "pkg1":
            return pkg1_team
        elif _team == "team":
            return team
        elif _team == "new-team":
            return new_team
        else:
            assert False, "get_team_by_slug called with wrong team " + _team + "!"

    meta = mock.MagicMock()
    meta.meta = {
        "extra": {
            "recipe-maintainers": [
                "user1",
                "user2",
                "org-name/team",
                "user3",
                "org-name/new-team",
            ]
        }
    }

    gh_repo = mock.MagicMock(spec=github.Repository.Repository)
    gh_repo.get_teams.return_value = [team, pkg1_team]

    org = mock.MagicMock(spec=github.Organization.Organization)
    org.login = "org-name"
    org.get_team_by_slug.side_effect = get_team_by_slug_return
    feedstock_name = "pkg1"  # without '-feedstock'

    gh = mock.MagicMock(spec=github.Github)
    gh_file_pull.return_value = '{"user1": 1, "user2": 2}'
    gh.get_user.side_effect = gh_get_user_return

    has_in_members.return_value = False

    configure_github_team(meta, gh_repo, org, feedstock_name, remove=True, gh=gh)

    gh_file_pull.assert_called_once_with(gh_repo, ".recipe_maintainers.json")
    gh_repo.get_teams.assert_called_once_with()
    org.get_team_by_slug.assert_has_calls(
        [
            mock.call("new-team"),
            mock.call("pkg1"),
        ]
    )
    create_team.assert_not_called()
    get_cached_team.assert_called_once()  # do not bother to check call here
    add_membership.assert_has_calls(
        [
            mock.call(pkg1_team, "user3"),
            mock.call(get_cached_team.return_value, "user3"),
        ],
        any_order=True,
    )
    has_in_members.assert_has_calls(
        [
            mock.call(get_cached_team.return_value, "user3"),
        ],
        any_order=True,
    )
    remove_membership.assert_not_called()
    team.add_to_repos.assert_not_called()
    new_team.add_to_repos.assert_called_once_with(gh_repo)
    org.get_team_by_slug.return_value.remove_from_repos.assert_not_called()

    gh_file_push.assert_called_once_with(
        gh_repo,
        ".recipe_maintainers.json",
        json.dumps({"user1": 1, "user2": 2, "user3": 3}, sort_keys=True, indent=2),
        "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** add/remove IDs for maintainers ['user3']",
    )


@mock.patch("conda_smithy.github.has_in_members")
@mock.patch("conda_smithy.github.remove_membership")
@mock.patch("conda_smithy.github.add_membership")
@mock.patch("conda_smithy.github.get_cached_team")
@mock.patch("conda_smithy.github.create_team")
@mock.patch("conda_smithy.github.push_file_via_gh_api")
@mock.patch("conda_smithy.github.pull_file_via_gh_api")
def test_github_configure_github_team_add_user_changed_id(
    gh_file_pull,
    gh_file_push,
    create_team,
    get_cached_team,
    add_membership,
    remove_membership,
    has_in_members,
    caplog,
):

    def gh_get_user_return(name):
        if name != "user2":
            mck = mock.MagicMock()
            mck.id = int(name.replace("user", ""))
            return mck
        else:
            mck = mock.MagicMock()
            mck.id = 10
            return mck

    team = mock.MagicMock()
    team.slug = "team"

    pkg1_team = mock.MagicMock()
    pkg1_team.slug = "pkg1"
    pkg1_team.name = "pkg1"
    user1 = mock.MagicMock()
    user1.login = "user1"
    pkg1_team.get_members.return_value = [
        user1,
    ]

    new_team = mock.MagicMock()
    new_team.slug = "new-team"

    def get_team_by_slug_return(_team):
        if _team == "pkg1":
            return pkg1_team
        elif _team == "team":
            return team
        elif _team == "new-team":
            return new_team
        else:
            assert False, "get_team_by_slug called with wrong team " + _team + "!"

    meta = mock.MagicMock()
    meta.meta = {
        "extra": {
            "recipe-maintainers": [
                "user1",
                "user2",
                "org-name/team",
                "user3",
                "org-name/new-team",
            ]
        }
    }

    gh_repo = mock.MagicMock(spec=github.Repository.Repository)
    gh_repo.get_teams.return_value = [team, pkg1_team]

    org = mock.MagicMock(spec=github.Organization.Organization)
    org.login = "org-name"
    org.get_team_by_slug.side_effect = get_team_by_slug_return
    feedstock_name = "pkg1"  # without '-feedstock'

    gh = mock.MagicMock(spec=github.Github)
    gh_file_pull.return_value = '{"user1": 1, "user2": 2}'
    gh.get_user.side_effect = gh_get_user_return

    has_in_members.return_value = False

    configure_github_team(meta, gh_repo, org, feedstock_name, remove=True, gh=gh)

    assert any(
        "Did not add user 'user2' since new id '10'" in record.message
        for record in caplog.records
    )

    gh_file_pull.assert_called_once_with(gh_repo, ".recipe_maintainers.json")
    gh_repo.get_teams.assert_called_once_with()
    org.get_team_by_slug.assert_has_calls(
        [
            mock.call("new-team"),
            mock.call("pkg1"),
        ]
    )
    create_team.assert_not_called()
    get_cached_team.assert_called_once()  # do not bother to check call here
    add_membership.assert_has_calls(
        [
            mock.call(pkg1_team, "user3"),
            mock.call(get_cached_team.return_value, "user3"),
        ],
        any_order=True,
    )
    has_in_members.assert_has_calls(
        [
            mock.call(get_cached_team.return_value, "user3"),
        ],
        any_order=True,
    )
    remove_membership.assert_not_called()
    team.add_to_repos.assert_not_called()
    new_team.add_to_repos.assert_called_once_with(gh_repo)
    org.get_team_by_slug.return_value.remove_from_repos.assert_not_called()

    gh_file_push.assert_called_once_with(
        gh_repo,
        ".recipe_maintainers.json",
        json.dumps({"user1": 1, "user2": 2, "user3": 3}, sort_keys=True, indent=2),
        "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** add/remove IDs for maintainers ['user3']",
    )


@mock.patch("conda_smithy.github.has_in_members")
@mock.patch("conda_smithy.github.remove_membership")
@mock.patch("conda_smithy.github.add_membership")
@mock.patch("conda_smithy.github.get_cached_team")
@mock.patch("conda_smithy.github.create_team")
@mock.patch("conda_smithy.github.push_file_via_gh_api")
@mock.patch("conda_smithy.github.pull_file_via_gh_api")
def test_github_configure_github_team_add_changed_user_id_team_remove(
    gh_file_pull,
    gh_file_push,
    create_team,
    get_cached_team,
    add_membership,
    remove_membership,
    has_in_members,
    caplog,
):

    def gh_get_user_return(name):
        if name not in ("user2", "user4", "user5", "user11"):
            mck = mock.MagicMock()
            mck.id = int(name.replace("user", ""))
        elif name == "user2":
            mck = mock.MagicMock()
            mck.id = 10
        elif name == "user11":
            mck = mock.MagicMock()
            mck.id = 4
        elif name in ("user4", "user5"):
            raise RuntimeError("Failure to get user id for user 4/5!")

        return mck

    team = mock.MagicMock()
    team.slug = "team"

    pkg1_team = mock.MagicMock()
    pkg1_team.slug = "pkg1"
    pkg1_team.name = "pkg1"
    user1 = mock.MagicMock()
    user1.login = "user1"
    user411 = mock.MagicMock()
    user411.login = "user11"
    pkg1_team.get_members.return_value = [
        user1,
        user411,
    ]

    new_team = mock.MagicMock()
    new_team.slug = "new-team"

    def get_team_by_slug_return(_team):
        if _team == "pkg1":
            return pkg1_team
        elif _team == "team":
            return team
        elif _team == "new-team":
            return new_team
        else:
            assert False, "get_team_by_slug called with wrong team " + _team + "!"

    meta = mock.MagicMock()
    meta.meta = {
        "extra": {
            "recipe-maintainers": [
                "user2",
                "user3",
                "user4",
                "user5",
                "org-name/new-team",
            ]
        }
    }

    gh_repo = mock.MagicMock(spec=github.Repository.Repository)
    gh_repo.get_teams.return_value = [team, pkg1_team]

    org = mock.MagicMock(spec=github.Organization.Organization)
    org.login = "org-name"
    org.get_team_by_slug.side_effect = get_team_by_slug_return
    feedstock_name = "pkg1"  # without '-feedstock'

    gh = mock.MagicMock(spec=github.Github)
    gh_file_pull.return_value = '{"user1": 1, "user2": 2, "user4": 4}'
    gh.get_user.side_effect = gh_get_user_return

    has_in_members.return_value = False

    configure_github_team(meta, gh_repo, org, feedstock_name, remove=True, gh=gh)

    assert any(
        "Did not add user 'user2' since new id '10'" in record.message
        for record in caplog.records
    )
    assert any(
        "Could not get user ID for user 'user5'!" in record.message
        for record in caplog.records
    )

    gh_file_pull.assert_called_once_with(gh_repo, ".recipe_maintainers.json")
    gh_repo.get_teams.assert_called_once_with()
    org.get_team_by_slug.assert_has_calls(
        [
            mock.call("new-team"),
            mock.call("team"),
            mock.call("pkg1"),
        ],
        any_order=True,
    )
    create_team.assert_not_called()
    get_cached_team.assert_called_once()  # do not bother to check call here
    add_membership.assert_has_calls(
        [
            mock.call(pkg1_team, "user3"),
            mock.call(get_cached_team.return_value, "user3"),
        ],
        any_order=True,
    )
    has_in_members.assert_has_calls(
        [
            mock.call(get_cached_team.return_value, "user3"),
        ],
        any_order=True,
    )
    # FIXME - if we do not remove renamed folks, then the test should
    # only remove user 1
    # remove_membership.assert_called_once_with(pkg1_team, "user1")
    remove_membership.assert_has_calls(
        [
            mock.call(pkg1_team, "user1"),
            mock.call(pkg1_team, "user11"),
        ],
        any_order=True,
    )
    team.add_to_repos.assert_not_called()
    team.remove_from_repos.assert_called_once_with(gh_repo)
    new_team.add_to_repos.assert_called_once_with(gh_repo)
    org.get_team_by_slug.return_value.remove_from_repos.assert_not_called()

    gh_file_push.assert_called_once_with(
        gh_repo,
        ".recipe_maintainers.json",
        json.dumps({"user2": 2, "user3": 3, "user4": 4}, sort_keys=True, indent=2),
        "[ci skip] [skip ci] [cf admin skip] ***NO_CI*** add/remove IDs for maintainers ['user3']",
    )
