import pytest
from textwrap import dedent

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

