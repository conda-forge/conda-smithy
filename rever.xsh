import os

$PROJECT = $GITHUB_REPO = 'conda-smithy'
$GITHUB_ORG = 'conda-forge'

$ACTIVITIES = ['authors', 'changelog', 'tag', 'push_tag', 'ghrelease', 'conda_forge']

$AUTHORS_FILENAME = 'AUTHORS.rst'
$CHANGELOG_FILENAME = 'CHANGELOG.rst'
$CHANGELOG_TEMPLATE = 'TEMPLATE.rst'

def sdist_asset():
    fname = os.path.join('dist', 'conda-smithy-' + $VERSION + '.tar.gz')
    print('Creating sdist tarball ' + fname)
    ![python setup.py sdist]
    return fname

$TAG_TEMPLATE = $GHRELEASE_NAME = 'v$VERSION'
$GHRELEASE_ASSETS = [sdist_asset]
$CONDA_FORGE_SOURCE_URL = ('https://github.com/conda-forge/conda-smithy/releases/'
                           'download/v$VERSION/conda-smithy-$VERSION.tar.gz')
