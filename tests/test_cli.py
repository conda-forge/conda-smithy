import argparse
import collections
import os
import subprocess

from conda_smithy import cli

_thisdir = os.path.abspath(os.path.dirname(__file__))


def test_init(py_recipe):
    """This is the command that takes the initial staged-recipe folder and turns it into a
    feedstock"""
    # actual parser doesn't matter.  It's used for initialization only
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()
    init_obj = cli.Init(subparser)
    recipe = py_recipe.recipe
    # expected args object has
    ArgsObject = collections.namedtuple('ArgsObject', ('no_git_repo',
                                                       'recipe_directory',
                                                       'feedstock_directory',
                                                       'variant_config_files'))
    args = ArgsObject(recipe_directory=os.path.join(recipe, 'recipe'),
                      feedstock_directory=os.path.join(recipe, '{package}-feedstock'),
                      no_git_repo=False,
                      variant_config_files=os.path.join(recipe, 'config.yaml'))
    init_obj(args)
    destination = os.path.join(recipe, 'py-test-feedstock')
    assert os.path.isdir(destination)


def test_regenerate(py_recipe):
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()
    regen_obj = cli.Regenerate(subparser)
    recipe = py_recipe.recipe
    ArgsObject = collections.namedtuple('ArgsObject', ('commit',
                                                       'feedstock_directory',
                                                       'variant_config_files'))
    feedstock_dir = os.path.join(_thisdir, 'recipes', 'click-test-feedstock')
    args = ArgsObject(feedstock_directory=feedstock_dir,
                      commit=False,
                      variant_config_files=os.path.join(recipe, 'config.yaml'))
    matrix_folder = os.path.join(feedstock_dir, 'ci_support', 'matrix')
    try:
        # original rendering was with py27, 36, no target_platform
        assert len(os.listdir(matrix_folder)) == 7
        regen_obj(args)
        # should add 2, as the config.yaml adds in target_platform
        assert len(os.listdir(matrix_folder)) == 9

        # reduce the python matrix and make sure the matrix files reflect the change
        args = ArgsObject(feedstock_directory=feedstock_dir,
                          commit=False,
                          variant_config_files=os.path.join(recipe, 'short_config.yaml'))
        matrix_folder = os.path.join(feedstock_dir, 'ci_support', 'matrix')
        # one py ver, no target_platform  (tests that older configs don't stick around)
        regen_obj(args)
        assert len(os.listdir(matrix_folder)) == 4
    finally:
        # reset the test dir for next time
        subprocess.call(['git', 'reset', '--hard', 'eab174eff9ac7d3a593b8dc6f11c2c8862a7b1ff'],
                        cwd=feedstock_dir)
