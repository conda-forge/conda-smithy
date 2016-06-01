#!/usr/bin/env python
from __future__ import print_function
import os
import requests
import time

import ruamel.yaml

from .vendored import travis_encrypt as travis
from . import github


# https://circleci.com/docs/api#add-environment-variable

# curl -X POST --header "Content-Type: application/json" -d '{"name":"foo", "value":"bar"}'
# https://circleci.com/api/v1/project/:username/:project/envvar?circle-token=:token

try:
    # Create a token at https://circleci.com/account/api. Put it in circle.token
    with open(os.path.expanduser('~/.conda-smithy/circle.token'), 'r') as fh:
        circle_token = fh.read().strip()
except IOError:
    print('No circle token.  Create a token at https://circleci.com/account/api and\n'
          'put it in ~/.conda-smithy/circle.token')

try:
    with open(os.path.expanduser('~/.conda-smithy/appveyor.token'), 'r') as fh:
        appveyor_token = fh.read().strip()
except IOError:
    print('No appveyor token. Create a token at https://ci.appveyor.com/api-token and\n'
          'Put one in ~/.conda-smithy/appveyor.token')

try:
    anaconda_token = os.environ['BINSTAR_TOKEN']
except KeyError:
    try:
        with open(os.path.expanduser('~/.conda-smithy/anaconda.token'), 'r') as fh:
            anaconda_token = fh.read().strip()
    except IOError:
        print('No anaconda token. Create a token via\n'
              '  anaconda auth --create --name conda-smithy --scopes "repos conda api"'
              'and put it in ~/.conda-smithy/anaconda.token')

def add_token_to_circle(user, project):
    url_template = ('https://circleci.com/api/v1/project/{user}/{project}/envvar?'
                    'circle-token={token}')
    url = url_template.format(token=circle_token, user=user, project=project)
    data = {'name': 'BINSTAR_TOKEN', 'value': anaconda_token}
    response = requests.post(url, data)
    if response.status_code != 201:
        raise ValueError(response)


def add_project_to_circle(user, project):
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    url_template = ('https://circleci.com/api/v1/{component}?'
                    'circle-token={token}')

    # Note, we used to check to see whether the project was already registered, but it started
    # timing out once we had too many repos, so now the approach is simply "add it always".

    url = url_template.format(component='project/{}/{}/follow'.format(user, project).lower(), token=circle_token)
    response = requests.post(url, headers={})
    # It is a strange response code, but is doing what was asked...
    if response.status_code != 400:
        response.raise_for_status()
    print(' * {}/{} enabled on CircleCI'.format(user, project))


def add_project_to_appveyor(user, project):
    headers = {'Authorization': 'Bearer {}'.format(appveyor_token),
               }
    url = 'https://ci.appveyor.com/api/projects'

    response = requests.get(url, headers=headers)
    if response.status_code != 201:
        response.raise_for_status()
    repos = [repo['repositoryName'].lower() for repo in response.json()]

    if '{}/{}'.format(user, project).lower() in repos:
        print(' * {}/{} already enabled on appveyor'.format(user, project))
    else:
        data = {'repositoryProvider': 'gitHub', 'repositoryName': '{}/{}'.format(user, project)}
        response = requests.post(url, headers=headers, data=data)
        if response.status_code != 201:
            response.raise_for_status()
        print(' * {}/{} has been enabled on appveyor'.format(user, project))


def appveyor_encrypt_binstar_token(feedstock_directory, user, project):
    headers = {'Authorization': 'Bearer {}'.format(appveyor_token)}
    url = 'https://ci.appveyor.com/api/account/encrypt'
    response = requests.post(url, headers=headers, data={"plainValue": anaconda_token})
    if response.status_code != 200:
        raise ValueError(response)

    forge_yaml = os.path.join(feedstock_directory, 'conda-forge.yml')
    if os.path.exists(forge_yaml):
        with open(forge_yaml, 'r') as fh:
            code = ruamel.yaml.load(fh, ruamel.yaml.RoundTripLoader)
    else:
        code = {}

    # Code could come in as an empty list.
    if not code:
        code = {}

    code.setdefault('appveyor', {}).setdefault('secure', {})['BINSTAR_TOKEN'] = response.content.decode('utf-8')
    with open(forge_yaml, 'w') as fh:
        fh.write(ruamel.yaml.dump(code, Dumper=ruamel.yaml.RoundTripDumper))


def appveyor_configure(user, project):
    """Configure appveyor so that it skips building if there is no appveyor.yml present."""
    headers = {'Authorization': 'Bearer {}'.format(appveyor_token)}
    # I have reasons to believe this is all AppVeyor is doing to the API URL.
    project = project.replace('_', '-').replace('.', '-')
    url = 'https://ci.appveyor.com/api/projects/{}/{}/settings'.format(user, project)
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise ValueError(response)
    content = response.json()
    settings = content['settings']
    skip_appveyor = u'skipBranchesWithoutAppveyorYml'
    print('{: <30}: Current setting for {} = {}.'
          ''.format(project, skip_appveyor, settings[skip_appveyor]))
    settings[skip_appveyor] = True
    url = 'https://ci.appveyor.com/api/projects'.format(user, project)

    response = requests.put(url, headers=headers, json=settings)
    if response.status_code != 204:
        raise ValueError(response)


def add_project_to_travis(user, project):
    headers = {
               # If the user-agent isn't defined correctly, we will recieve a 403.
               'User-Agent': 'MyClient/1.0.0',
               'Accept': 'application/vnd.travis-ci.2+json',
               }
    endpoint = 'https://api.travis-ci.org'
    url = '{}/auth/github'.format(endpoint)
    data = {"github_token": github.gh_token()}
    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 201:
        response.raise_for_status()

    token = response.json()['access_token']
    headers['Authorization'] = 'token {}'.format(token)

    url = '{}/hooks'.format(endpoint)

    found = False
    count = 0

    while not found:
        count += 1

        response = requests.get(url, headers=headers)
        content = response.json()
        try:
            found = [hooked for hooked in content['hooks']
                     if hooked['owner_name'] == user and hooked['name'] == project]
        except KeyError:
            pass

        if not found:
            if count == 1:
                print(" * Travis doesn't know about the repo, synching (takes a few seconds).")
                synch_url = '{}/users/sync'.format(endpoint)
                response = requests.post(synch_url, headers=headers)
            time.sleep(3)

        if count > 20:
            msg = ('Unable to register the repo on Travis\n'
                   '(Is it down? Is the "{}" name spelt correctly? [note: case sensitive])')
            raise RuntimeError(msg.format(user))

    if found[0]['active'] is True:
        print(' * {}/{} already enabled on travis-ci'.format(user, project))
    else:
        repo_id = found[0]['id']
        url = '{}/hooks'.format(endpoint)
        response = requests.put(url, headers=headers, json={'hook': {'id': repo_id, 'active': True}})
        if response.json().get('result'):
            print(' * Registered on travis-ci')
        else:
            raise RuntimeError('Unable to register on travis-ci, response from hooks was negative')
        url = '{}/users/sync'.format(endpoint)
        response = requests.post(url, headers=headers)


def travis_token_update_conda_forge_config(feedstock_directory, user, project):
    item = 'BINSTAR_TOKEN="{}"'.format(anaconda_token)
    slug = "{}/{}".format(user, project)

    forge_yaml = os.path.join(feedstock_directory, 'conda-forge.yml')
    if os.path.exists(forge_yaml):
        with open(forge_yaml, 'r') as fh:
            code = ruamel.yaml.load(fh, ruamel.yaml.RoundTripLoader)
    else:
        code = {}

    # Code could come in as an empty list.
    if not code:
        code = {}

    code.setdefault('travis', {}).setdefault('secure', {})['BINSTAR_TOKEN'] = (
        _encrypt_binstar_token(slug, item)
    )
    with open(forge_yaml, 'w') as fh:
        fh.write(ruamel.yaml.dump(code, Dumper=ruamel.yaml.RoundTripDumper))


def _encrypt_binstar_token(slug, item):
    return travis.encrypt(slug, item.encode()).decode('utf-8')


def add_conda_linting(user, repo):
    if user != 'conda-forge':
        print('Unable to register {}/{} for conda-linting at this time as only '
              'conda-forge repos are supported.'.format(user, repo))

    headers = {'Authorization': 'token {}'.format(github.gh_token())}
    url = 'https://api.github.com/repos/{}/{}/hooks'.format(user, repo)

    # Get the current hooks to determine if anything needs doing.
    response = requests.get(url, headers=headers)
    registered = response.json()
    hook_by_url = {hook['config'].get('url'): hook for hook in registered
                   if 'url' in hook['config']}

    hook_url = "http://conda-forge.herokuapp.com/conda-linting/hook"

    payload = {
          "name": "web",
          "active": True,
          "events": [
            "pull_request"
          ],
          "config": {
            "url": hook_url,
            "content_type": "json"
          }
        }

    if hook_url not in hook_by_url:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            response.raise_for_status()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("user")
    parser.add_argument("project")
    args = parser.parse_args(['conda-forge', 'conda-smithy-feedstock'])

#    add_project_to_circle(args.user, args.project)
#    add_project_to_appveyor(args.user, args.project)
#    add_project_to_travis(args.user, args.project)
#    appveyor_encrypt_binstar_token('../udunits-delme-feedstock', args.user, args.project)
#    appveyor_configure('conda-forge', 'glpk-feedstock')
#    travis_token_update_conda_forge_config('../udunits-delme-feedstock', args.user, args.project)
    add_conda_linting(args.user, 'matplotlib-feedstock')
    print('Done')
