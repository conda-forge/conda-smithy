import pytest

from conda_smithy.lint_artifact import check_path_patterns


def test_unix_fhs_paths():
    paths = [
        "bin/executable",
        "lib/libsomething.so",
        "include/header.h",
        "etc/config-file",
        "share/data-stuff",
    ]
    errors, warnings = check_path_patterns(paths=paths)
    assert not errors
    assert not warnings

    paths.append("random-top-level-directory/file")
    errors, warnings = check_path_patterns(paths=paths)
    assert errors


def test_windows_paths():
    paths = [
        "bin/executable",
        "lib/libsomething.so",
        "include/header.h",
        "etc/config-file",
        "share/data-stuff",
        "Library/bin/something.exe",
    ]
    index = {"subdir": "win-64"}
    errors, warnings = check_path_patterns(paths=paths, index=index)
    assert not errors
    assert not warnings

    errors, warnings = check_path_patterns(paths=paths)
    assert len(errors) == 1
    assert list(errors.values())[0] == ["Library/bin/something.exe"]
    assert not warnings


def test_noarch_python_exceptions():
    paths = [
        "site-packages/numpy/__init__.py",
    ]
    index = {"noarch": "python"}
    errors, warnings = check_path_patterns(paths=paths, index=index)
    assert not errors
    assert not warnings

    errors, warnings = check_path_patterns(paths=paths)
    assert errors
    assert not warnings


@pytest.mark.parametrize("name", ["openssl", "ca-certificates"])
def test_ssl_exceptions(name):
    paths = [
        "ssl/security-stuff",
    ]
    index = {"name": name}
    errors, warnings = check_path_patterns(paths=paths, index=index)
    assert not errors
    assert not warnings

    errors, warnings = check_path_patterns(paths=paths)
    assert errors
    assert not warnings


@pytest.mark.parametrize("name", ["conda", "mamba"])
def test_conda_exceptions(name):
    paths = [
        f"condabin/{name}",
    ]
    index = {"name": name}
    errors, warnings = check_path_patterns(paths=paths, index=index)
    assert not errors
    assert not warnings

    errors, warnings = check_path_patterns(paths=paths)
    assert errors
    assert not warnings
