

def add_token_to_circle(user, project):
    url_template = (
        "https://circleci.com/api/v1.1/project/github/{user}/{project}/envvar?"
        "circle-token={token}"
    )
    url = url_template.format(token=circle_token, user=user, project=project)
    data = {"name": "BINSTAR_TOKEN", "value": anaconda_token}
    response = requests.post(url, data)
    if response.status_code != 201:
        raise ValueError(response)


def add_token_to_drone(user, project):
    session = drone_session()
    response = session.post(
        f"/api/repos/{user}/{project}/secrets",
        json={
            "name": "BINSTAR_TOKEN",
            "data": anaconda_token,
            "pull_request": False,
        },
    )
    if response.status_code != 200:
        # Check that the token is in secrets already
        session = drone_session()
        response2 = session.get(f"/api/repos/{user}/{project}/secrets")
        response2.raise_for_status()
        for secret in response2.json():
            if "BINSTAR_TOKEN" == secret["name"]:
                return
    response.raise_for_status()


def appveyor_encrypt_binstar_token(feedstock_directory, user, project):
    headers = {"Authorization": "Bearer {}".format(appveyor_token)}
    url = "https://ci.appveyor.com/api/account/encrypt"
    response = requests.post(
        url, headers=headers, data={"plainValue": anaconda_token}
    )
    if response.status_code != 200:
        raise ValueError(response)

    with update_conda_forge_config(feedstock_directory) as code:
        code.setdefault("appveyor", {}).setdefault("secure", {})[
            "BINSTAR_TOKEN"
        ] = response.content.decode("utf-8")
