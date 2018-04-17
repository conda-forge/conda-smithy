import os

$PROJECT = $GITHUB_REPO = 'conda-smithy'
$GITHUB_ORG = 'conda-forge'

$ACTIVITIES = ['tag', 'push_tag', 'ghrelease']


def sdist_asset():
    fname = os.path.join('dist', 'conda-smithy-' + $VERSION + '.tar.gz')
    print('Creating sdist tarball ' + fname)
    ![python setup.py sdist]
    return fname


$GHRELEASE_ASSETS = [sdist_asset]
