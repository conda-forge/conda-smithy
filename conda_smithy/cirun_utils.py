from cirun import Cirun


def ensure_cirun_app_installed(owner, repo):
    "Install the cirun.io app for this owner (user or org). Only the first time."
    pass


def enable_cirun_for_project(owner, project):
    """Enable the cirun.io app for a particular repository."""
    cirun = _get_cirun_client()
    return cirun.set_repo(f"{owner}/{project}", installation_id=123)


def disable_cirun_for_project(owner, project):
    """Disable the cirun.io app for a particular repository."""
    cirun = _get_cirun_client()
    return cirun.set_repo(f"{owner}/{project}", active=False)


def add_project_to_cirun_resource(owner, project, resource):
    """Grant access to a cirun resource to a particular repository, with a particular policy."""
    cirun = _get_cirun_client()
    cirun.add_repo_to_resources("conda-forge", project, resource)


def revoke_access_to_cirun_resource(owner, project, resource):
    """Revoke access to a cirun resource to a particular repository, with a particular policy."""
    cirun = _get_cirun_client()
    cirun.remove_repo_from_resources("conda-forge", project, [resource])


def enabled_cirun_resources(owner, project):
    """Which resources are currently enabled for this project"""
    cirun = _get_cirun_client()
    return cirun.get_repo_resources("conda-forge", project)


def remove_project_from_cirun_resource(owner, repo, resource):
    revoke_access_to_cirun_resource(owner, project=repo, resource=resource)


def remove_project_from_cirun(owner, repo):
    pass


def _get_cirun_client():
    try:
        return Cirun()
    except KeyError:
        raise RuntimeError(
            "You must have CIRUN_API_KEY defined to do Cirun CI registration"
            "This requirement can be overriden by specifying `--without-cirun`"
        )
