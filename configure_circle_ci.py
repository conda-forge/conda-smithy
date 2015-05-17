#!/usr/bin/env python
import os
import requests


# https://circleci.com/docs/api#add-environment-variable

# curl -X POST --header "Content-Type: application/json" -d '{"name":"foo", "value":"bar"}'
# https://circleci.com/api/v1/project/:username/:project/envvar?circle-token=:token

# Create a token at https://circleci.com/account/api. Put it in circle.token
with open('circle.token', 'r') as fh:
    circle_token = fh.read().strip()

with open('appveyor.token', 'r') as fh:
    appveyor_token = fh.read().strip()



def add_BINSTAR_TOKEN_to_circle(user, project):
    url_template = ('https://circleci.com/api/v1/project/{user}/{project}/envvar?'
                    'circle-token={token}')
    url = url_template.format(token=circle_token, user=user, project=project)
    data = {'name': 'BINSTAR_TOKEN', 'value': os.environ['BINSTAR_TOKEN']}
    response = requests.post(url, data)
    if response.status_code != 201:
        raise ValueError(response)


def add_project_to_circle(user, project):
    url_template = ('https://circleci.com/api/v1/projects?'
                    'circle-token={token}')
    url = url_template.format(token=circle_token)
    data = {'username': user, 'reponame': project}
    response = requests.post(url, data)
    if response.status_code != 201:
        response.raise_for_status()


def add_project_to_appveyor(user, project):
    headers = {'Authorization': 'Basic {}'.format(appveyor_token),
               'Content-Type': 'application/json'}
#     headers = {}
    print headers
    url = 'https://ci.appveyor.com/api/projects'
#     url = 'https://ci.appveyor.com/api/users'
    url = 'https://ci.appveyor.com/api/roles'

    data = {'repositoryProvider': 'gitHub', 'repositoryName': '{}/{}'.format(user, project)}
    print data
#     response = requests.post(url, headers=headers, data=data)
    response = requests.get(url, headers=headers)
    print 'Content: ', response.raw.read()
    if response.status_code != 201:
        response.raise_for_status()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("user")
    parser.add_argument("project")
    args = parser.parse_args(['pelson', 'udunits-feedstock'])
    add_project_to_appveyor(args.user, args.project)
    print 'Done'
