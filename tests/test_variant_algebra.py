from textwrap import dedent

import pytest

from conda_smithy.variant_algebra import parse_variant, variant_add

tv1 = parse_variant(
    """\
foo:
    - 1.10
bar:
    - 2
"""
)

tv2 = parse_variant(
    """\
foo:
    - 1.2
bar:
    - 3
"""
)

tv3 = parse_variant(
    """\
baz:
    - 1
bar:
    - 3
"""
)

tv4 = parse_variant(
    """\
baz:
    - 1
bar:
    - 0
    - 6
"""
)


def test_add():
    variant_add(tv1, tv2)

    # %%

    variant_add(tv1, tv3)

    # %%

    variant_add(tv2, tv3)
    # %%

    variant_add(tv1, variant_add(tv2, tv3))

    # %%

    variant_add(tv1, tv4)

    # %%

    variant_add(tv4, tv1)


def test_ordering():
    start = parse_variant(
        dedent(
            """\
    c_compiler:
        - toolchain
    """
        )
    )

    mig_compiler = parse_variant(
        dedent(
            """\
    __migrator:
        ordering:
            c_compiler:
                - toolchain
                - gcc
    c_compiler:
        - gcc
    """
        )
    )

    res = variant_add(start, mig_compiler)
    assert res["c_compiler"] == ["gcc"]
    print(res)
    # raise Exception()


def test_no_ordering():
    start = parse_variant(
        dedent(
            """\
    xyz:
        - 1
    """
        )
    )

    mig_compiler = parse_variant(
        dedent(
            """\
    __migrator:
        kind:
            version
        migration_no:
            1
    xyz:
        - 2
    """
        )
    )

    res = variant_add(start, mig_compiler)
    assert res["xyz"] == ["2"]
    print(res)
    # raise Exception()


def test_ordering_downgrade():
    start = parse_variant(
        dedent(
            """\
    jpeg:
        - 3.0
    """
        )
    )

    mig_compiler = parse_variant(
        dedent(
            """\
    __migrator:
        ordering:
            jpeg:
                - 3.0
                - 2.0
    jpeg:
        - 2.0
    """
        )
    )

    res = variant_add(start, mig_compiler)
    assert res["jpeg"] == ["2.0"]
    print(res)


def test_ordering_space():
    start = parse_variant(
        dedent(
            """\
    python:
        - 2.7
    """
        )
    )

    mig_compiler = parse_variant(
        dedent(
            """\
    python:
        - 2.7 *_cpython
    """
        )
    )

    res = variant_add(start, mig_compiler)
    assert res["python"] == ["2.7 *_cpython"]
    print(res)


def test_new_pinned_package():
    start = parse_variant(
        dedent(
            """\
    pin_run_as_build:
        jpeg:
            max_pin: x
    jpeg:
        - 3.0
    """
        )
    )

    mig_compiler = parse_variant(
        dedent(
            """\
    pin_run_as_build:
        gprc-cpp:
            max_pin: x.x
    gprc-cpp:
        - 1.23
    """
        )
    )

    res = variant_add(start, mig_compiler)
    assert res["gprc-cpp"] == ["1.23"]
    assert res["pin_run_as_build"]["gprc-cpp"]["max_pin"] == "x.x"
    print(res)


def test_zip_keys():
    start = parse_variant(
        dedent(
            """\
    zip_keys:
        -
            - vc
            - python
        -
            - qt
            - pyqt
    """
        )
    )

    mig_compiler = parse_variant(
        dedent(
            """\
    zip_keys:
        -
            - python
            - vc
            - vc_runtime
        -
            - root
            - c_compiler
    """
        )
    )

    res = variant_add(start, mig_compiler)
    print(res)

    assert len(res["zip_keys"]) == 3
    assert ["python", "vc", "vc_runtime"] in res["zip_keys"]


def test_migrate_windows_compilers():
    start = parse_variant(
        dedent(
            """
        c_compiler:
            - vs2008
            - vs2015
        vc:
            - '9'
            - '14'
        zip_keys:
            - - vc
              - c_compiler
        """
        )
    )

    mig = parse_variant(
        dedent(
            """
        c_compiler:
            - vs2008
            - vs2017
        vc:
            - '9'
            - '14.1'
        """
        )
    )

    res = variant_add(start, mig)
    print(res)

    assert len(res["c_compiler"]) == 2
    assert res["c_compiler"] == ["vs2008", "vs2017"]
    assert len(res["zip_keys"][0]) == 2


def test_pin_run_as_build():
    start = parse_variant(
        dedent(
            """\
    pin_run_as_build:
        python:
            max_pin: x.x
        boost-cpp:
            max_pin: x
    """
        )
    )

    mig_compiler = parse_variant(
        dedent(
            """\
    pin_run_as_build:
        boost-cpp:
            max_pin: x.x
        rust:
            max_pin: x
    """
        )
    )

    res = variant_add(start, mig_compiler)
    print(res)

    assert len(res["pin_run_as_build"]) == 3


def test_py39_migration():
    """Test that running the python 3.9 keyadd migrator has the desired effect."""
    base = parse_variant(
        dedent(
            """
            python:
              - 3.6.* *_cpython    # [not (osx and arm64)]
              - 3.7.* *_cpython    # [not (osx and arm64)]
              - 3.8.* *_cpython
            python_impl:
              - cpython
            zip_keys:
              -
                - python
              -                             # ["linux-64"]
                - cuda_compiler_version     # ["linux-64"]
                - docker_image              # ["linux-64"]

            """
        )
    )

    migration_pypy = parse_variant(
        dedent(
            """
    python:
      - 3.6.* *_cpython   # [not (osx and arm64)]
      - 3.7.* *_cpython   # [not (osx and arm64)]
      - 3.8.* *_cpython
      - 3.6.* *_73_pypy   # [not (win64 or (osx and arm64))]

    numpy:
      - 1.16       # [not (osx and arm64)]
      - 1.16       # [not (osx and arm64)]
      - 1.16
      - 1.18       # [not (win64 or (osx and arm64))]

    python_impl:
      - cpython    # [not (osx and arm64)]
      - cpython    # [not (osx and arm64)]
      - cpython
      - pypy       # [not (win64 or (osx and arm64))]


    zip_keys:
      -
        - python
        - numpy
        - python_impl
    """
        )
    )

    migration_py39 = parse_variant(
        dedent(
            """
        __migrator:
            operation: key_add
            primary_key: python
            ordering:
                python:
                    - 3.6.* *_cpython
                    - 3.9.* *_cpython   # new entry
                    - 3.7.* *_cpython
                    - 3.8.* *_cpython
                    - 3.6.* *_73_pypy
        python:
          - 3.9.* *_cpython
        # additional entries to add for zip_keys
        numpy:
          - 1.100
        python_impl:
          - cpython
        """
        )
    )

    res = variant_add(base, migration_pypy)
    res2 = variant_add(res, migration_py39)

    print(res)
    print(res2)

    assert res2["python"] == migration_py39["__migrator"]["ordering"]["python"]
    # assert that we've ordered the numpy bits properly
    assert res2["numpy"] == [
        "1.16",
        "1.100",
        "1.16",
        "1.16",
        "1.18",
    ]

    res3 = variant_add(base, migration_py39)
    print(res3)
    assert res3["python"] == [
        "3.6.* *_cpython",
        "3.9.* *_cpython",  # newly added
        "3.7.* *_cpython",
        "3.8.* *_cpython",
    ]
    # The base doesn't have an entry for numpy
    assert "numpy" not in res3


def test_multiple_key_add_migration():
    """Test that running the python 3.9 keyadd migrator has the desired effect."""
    base = parse_variant(
        dedent(
            """
            python:
              - 3.6.* *_cpython    # [not (osx and arm64)]
              - 3.7.* *_cpython    # [not (osx and arm64)]
              - 3.8.* *_cpython
            python_impl:
              - cpython
            zip_keys:
              -
                - python
              -                             # ["linux-64"]
                - cuda_compiler_version     # ["linux-64"]
                - docker_image              # ["linux-64"]

            """
        )
    )

    migration_pypy = parse_variant(
        dedent(
            """
    python:
      - 3.6.* *_cpython   # [not (osx and arm64)]
      - 3.7.* *_cpython   # [not (osx and arm64)]
      - 3.8.* *_cpython
      - 3.6.* *_73_pypy   # [not (win64 or (osx and arm64))]

    numpy:
      - 1.16       # [not (osx and arm64)]
      - 1.16       # [not (osx and arm64)]
      - 1.16
      - 1.18       # [not (win64 or (osx and arm64))]

    python_impl:
      - cpython    # [not (osx and arm64)]
      - cpython    # [not (osx and arm64)]
      - cpython
      - pypy       # [not (win64 or (osx and arm64))]


    zip_keys:
      -
        - python
        - numpy
        - python_impl
    """
        )
    )

    migration_py39 = parse_variant(
        dedent(
            """
        __migrator:
            operation: key_add
            primary_key: python
            ordering:
                python:
                    - 3.6.* *_cpython
                    - 3.9.* *_cpython   # new entry
                    - 3.10.* *_cpython  # new entry
                    - 3.7.* *_cpython
                    - 3.8.* *_cpython
                    - 3.6.* *_73_pypy
        python:
          - 3.9.* *_cpython
          - 3.10.* *_cpython
        # additional entries to add for zip_keys
        numpy:
          - 1.100
          - 1.200
        python_impl:
          - cpython
          - cpython
        """
        )
    )

    res = variant_add(base, migration_pypy)
    res2 = variant_add(res, migration_py39)

    print(res)
    print(res2)

    assert res2["python"] == migration_py39["__migrator"]["ordering"]["python"]
    # assert that we've ordered the numpy bits properly
    assert res2["numpy"] == [
        "1.16",
        "1.100",
        "1.200",
        "1.16",
        "1.16",
        "1.18",
    ]

    res3 = variant_add(base, migration_py39)
    print(res3)
    assert res3["python"] == [
        "3.6.* *_cpython",
        "3.9.* *_cpython",  # newly added
        "3.10.* *_cpython",
        "3.7.* *_cpython",
        "3.8.* *_cpython",
    ]
    # The base doesn't have an entry for numpy
    assert "numpy" not in res3


def test_variant_key_remove():
    base = parse_variant(
        dedent(
            """
    python:
      - 3.6.* *_cpython
      - 3.8.* *_cpython
      - 3.6.* *_73_pypy
    numpy:
      - 1.16
      - 1.16
      - 1.18
    python_impl:
      - cpython
      - cpython
      - pypy
    zip_keys:
      -
        - python
        - numpy
        - python_impl
    """
        )
    )
    removal = parse_variant(
        dedent(
            """
            __migrator:
                operation: key_remove
                primary_key: python
                ordering:
                    python:
                        - 3.6.* *_73_pypy
                        - 3.6.* *_cpython
                        - 3.7.* *_cpython
                        - 3.8.* *_cpython
                        - 3.9.* *_cpython
            python:
              - 3.6.* *_cpython
            """
        )
    )

    res = variant_add(base, removal)

    assert res["python"] == ["3.6.* *_73_pypy", "3.8.* *_cpython"]
    assert res["numpy"] == ["1.18", "1.16"]
    assert res["python_impl"] == ["pypy", "cpython"]


@pytest.mark.parametrize(
    "platform,arch", [["osx", "64"], ["osx", "arm64"], ["linux", "64"]]
)
def test_variant_remove_add(platform, arch):
    from conda_build.config import Config

    config = Config(platform=platform, arch=arch)
    base = parse_variant(
        dedent(
            """
            python:
              - 3.7.* *_cpython   # [not (osx and arm64)]
              - 3.8.* *_cpython
              - 3.6.* *_73_pypy   # [not (win64 or (osx and arm64))]

            numpy:
              - 1.16       # [not (osx and arm64)]
              - 1.16
              - 1.18       # [not (win64 or (osx and arm64))]

            python_impl:
              - cpython    # [not (osx and arm64)]
              - cpython
              - pypy       # [not (win64 or (osx and arm64))]


            zip_keys:
              -
                - python
                - numpy
                - python_impl
            """
        ),
        config=config,
    )

    remove = parse_variant(
        dedent(
            """
            __migrator:
                operation: key_remove
                primary_key: python
            python:
              - 3.8.* *_cpython
            """
        ),
        config=config,
    )

    remove2 = parse_variant(
        dedent(
            """
            __migrator:
                operation: key_remove
                primary_key: python
            python:
              - 3.8.* *_cpython  # [(osx and arm64)]
            """
        ),
        config=config,
    )

    add = parse_variant(
        dedent(
            """
            __migrator:
                operation: key_add
                primary_key: python
            python:
              - 3.8.* *_cpython  # [not (osx and arm64)]
            numpy:
              - 1.16            # [not (osx and arm64)]
            python_impl:
              - cpython          # [not (osx and arm64)]
            """
        ),
        config=config,
    )

    add_py39 = parse_variant(
        dedent(
            """
        __migrator:
            operation: key_add
            primary_key: python
        python:
          - 3.9.* *_cpython
        # additional entries to add for zip_keys
        numpy:
          - 1.100
        python_impl:
          - cpython
        """
        )
    )

    res = variant_add(base, remove)
    res = variant_add(res, add)
    res = variant_add(res, add_py39)
    print(res["python"])
    print(res["numpy"])

    # alternatively we could just remove py38_osx-arm64 and then add py39
    res2 = variant_add(base, remove2)
    res2 = variant_add(res2, add_py39)
    assert res2 == res

    if (platform, arch) == ("osx", "arm64"):
        assert res["python"] == ["3.9.* *_cpython"]
    elif (platform, arch) in {("osx", "64"), ("linux", "64")}:
        assert res["python"] == [
            "3.6.* *_73_pypy",
            "3.7.* *_cpython",
            "3.8.* *_cpython",
            "3.9.* *_cpython",
        ]
    else:
        raise RuntimeError("Should have a check")
