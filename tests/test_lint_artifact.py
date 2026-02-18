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
        "python-scripts/numpy-script.py",
    ]
    index = {"noarch": "python"}
    errors, warnings = check_path_patterns(paths=paths, index=index)
    assert not errors
    assert not warnings

    errors, warnings = check_path_patterns(paths=paths)
    assert errors
    assert list(errors.values())[0] == paths
    assert not warnings


@pytest.mark.parametrize("name,n_errors", [("numpy", 0), ("test", 1), ("tests", 1)])
def test_disallowed_python_package_names(name, n_errors):
    paths = [
        f"site-packages/{name}/__init__.py",
    ]
    index = {"noarch": "python", "depends": ["python"]}
    errors, warnings = check_path_patterns(paths=paths, index=index)
    assert len(errors) == n_errors
    assert not warnings

    paths = [
        f"Lib/site-packages/{name}/__init__.py",
    ]
    index = {"subdir": "win-64", "depends": ["python"]}
    errors, warnings = check_path_patterns(paths=paths, index=index)
    assert len(errors) == n_errors
    assert not warnings

    paths = [
        f"lib/python3.10/site-packages/{name}/__init__.py",
    ]
    index = {"subdir": "linux-64"}
    errors, warnings = check_path_patterns(paths=paths)
    assert len(errors) == n_errors
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
