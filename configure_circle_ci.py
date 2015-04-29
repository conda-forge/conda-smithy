#!/usr/bin/env python
import os
import requests


# https://circleci.com/docs/api#add-environment-variable

# curl -X POST --header "Content-Type: application/json" -d '{"name":"foo", "value":"bar"}'
# https://circleci.com/api/v1/project/:username/:project/envvar?circle-token=:token

# Create a token at https://circleci.com/account/api. Put it in circle.token
with open('circle.token', 'r') as fh:
    token = fh.read().strip()

url_template = ('https://circleci.com/api/v1/project/{user}/{project}/envvar?'
                'circle-token={token}')



def add_BINSTAR_TOKEN_to_circle(user, project):
    url = url_template.format(token=token, user=user, project=project)
    data = {'name': 'BINSTAR_TOKEN', 'value': os.environ['BINSTAR_TOKEN']}
    response = requests.post(url, data)
    if response.status_code != 201:
        raise ValueError(response)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("user")
    parser.add_argument("project")
    args = parser.parse_args()
    add_BINSTAR_TOKEN_to_circle(args.user, args.project)
    print 'Done'