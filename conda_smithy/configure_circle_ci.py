#!/usr/bin/env python
from __future__ import print_function
import os
import requests


# https://circleci.com/docs/api#add-environment-variable

# curl -X POST --header "Content-Type: application/json" -d '{"name":"foo", "value":"bar"}'
# https://circleci.com/api/v1/project/:username/:project/envvar?circle-token=:token

try:
    # Create a token at https://circleci.com/account/api. Put it in circle.token
    with open(os.path.expanduser('~/.conda-smithy/circle.token'), 'r') as fh:
        circle_token = fh.read().strip()
except IOError:
    print('No circle token. Put one in ~/.conda-smithy/circle.token')

try:
    with open(os.path.expanduser('~/.conda-smithy/appveyor.token'), 'r') as fh:
        appveyor_token = fh.read().strip()
except IOError:
    print('No appveyor token. Put one in ~/.conda-smithy/appveyor.token')



def add_BINSTAR_TOKEN_to_circle(user, project):
    url_template = ('https://circleci.com/api/v1/project/{user}/{project}/envvar?'
                    'circle-token={token}')
    url = url_template.format(token=circle_token, user=user, project=project)
    data = {'name': 'BINSTAR_TOKEN', 'value': os.environ['BINSTAR_TOKEN']}
    response = requests.post(url, data)
    if response.status_code != 201:
        raise ValueError(response)


def add_project_to_circle(user, project):
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    url_template = ('https://circleci.com/api/v1/projects?'
                    'circle-token={token}')
    url = url_template.format(token=circle_token)
    data = {'username': user, 'reponame': project}
    response = requests.get(url, headers=headers)

    if response.status_code != 201:
        response.raise_for_status()

    repos = response.json()
    repos = ['{repo[username]}/repo[reponame]'.format(repo=repo).lower()
             for repo in repos]
    if '{}/{}'.format(user, project).lower() not in repos:
        # Apparently there is an endpoint for this, but it doesn't seem to work...
        print(' * Goto https://circleci.com/add-projects')
#         # Try adding it.
#         data = {'username': user, 'reponame': project}
#         response = requests.post(url, data, headers=headers)
#         if response.status_code != 201:
#             response.raise_for_status()
    else:
        print(' * {}/{} already enabled on CircleCI'.format(user, project))


def add_project_to_appveyor(user, project):
    headers = {'Authorization': 'Bearer {}'.format(appveyor_token),
               'Content-Type': 'application/json'}
    url = 'https://ci.appveyor.com/api/projects'

    response = requests.get(url, headers=headers)
    if response.status_code != 201:
        response.raise_for_status()
    repos = [repo['repositoryName'].lower() for repo in response.json()]

    if '{}/{}'.format(user, project).lower() in repos:
        print(' * {}/{} already enabled on appveyor'.format(user, project))
    else:
        # Apparently there is an endpoint for this, but it doesn't seem to work...
        print(' * Goto https://ci.appveyor.com/projects/new')
#         # Try adding it.
#         data = {'repositoryProvider': 'gitHub', 'repositoryName': '{}/{}'.format(user, project)}
#         response = requests.post(url, headers=headers, data=data)
#         if response.status_code != 201:
#             response.raise_for_status()


def add_project_to_travis(user, project):
    headers = {'User-Agent': 'conda-smithy',
              'Accept': 'application/vnd.travis-ci.2+json'}
    endpoint = 'https://api.travis-ci.org'
    url = '{}/auth/github'.format(endpoint)
    with open(os.path.expanduser('~/.conda-smithy/github.token'), 'r') as fh:
        github_token = fh.read().strip()
    data = {"github_token": github_token}
    response = requests.post(url, data=data, headers=headers)
    if response.status_code != 201:
        response.raise_for_status()

    token = response.json()['access_token']
    headers['Authorization'] = 'token {}'.format(token)

    url = '{}/repos/{}/{}'.format(endpoint, user, project)
    response = requests.get(url)
    content = response.json()
    found = 'id' in content

    if not found:
        # ... doesn't look like there is an endpoint for this.
        print(' * Goto https://travis-ci.org/profile/{} to register the project'.format(user))
    else:
        print(' * {}/{} already enabled on travis-ci'.format(user, project))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("user")
    parser.add_argument("project")
    args = parser.parse_args(['pelson', 'matplotlib'])
#     args = parser.parse_args(['conda-forge', 'udunits-feedstock'])

#     add_project_to_circle(args.user, args.project)
    add_project_to_appveyor(args.user, args.project)
#     add_project_to_travis(args.user, args.project)
    print('Done')
