from cirun import Cirun


def enable_cirun_for_project(owner, repo):
    """Enable the cirun.io Github Application for a particular repository."""
    cirun = _get_cirun_client()
    return cirun.set_repo(f"{owner}/{repo}", installation_id=123)


def disable_cirun_for_project(owner, repo):
    """Disable the cirun.io Github Application for a particular repository."""
    cirun = _get_cirun_client()
    return cirun.set_repo(f"{owner}/{repo}", active=False)


def enabled_cirun_resources(owner, repo):
    """Which resources are currently enabled for this project"""
    cirun = _get_cirun_client()
    return cirun.get_repo_resources("conda-forge", repo)


def add_repo_to_cirun_resource(repo, resource):
    """Grant access to a cirun resource to a particular repository, with a particular policy."""
    cirun = _get_cirun_client()
    cirun.add_repo_to_resources("conda-forge", repo, resource)


def remove_repo_from_cirun_resource(repo, resource):
    """Revoke access to a cirun resource to a particular repository, with a particular policy."""
    cirun = _get_cirun_client()
    cirun.remove_repo_from_resources("conda-forge", repo, [resource])


def _get_cirun_client():
    try:
        return Cirun()
    except KeyError:
        raise RuntimeError(
            "You must have CIRUN_API_KEY defined to do Cirun CI registration"
            "This requirement can be overriden by specifying `--without-cirun`"
        )
