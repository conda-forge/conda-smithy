import argparse
import collections
import os
import subprocess
import yaml

from conda_smithy import cli

_thisdir = os.path.abspath(os.path.dirname(__file__))

InitArgs = collections.namedtuple('ArgsObject', ('no_git_repo',
                                                 'recipe_directory',
                                                 'feedstock_directory',
                                                 'variant_config_files'))

RegenerateArgs = collections.namedtuple('ArgsObject', ('commit',
                                                       'feedstock_directory',
                                                       'variant_config_files'))


def test_init(py_recipe):
    """This is the command that takes the initial staged-recipe folder and turns it into a
    feedstock"""
    # actual parser doesn't matter.  It's used for initialization only
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()
    init_obj = cli.Init(subparser)
    recipe = py_recipe.recipe
    # expected args object has
    args = InitArgs(recipe_directory=os.path.join(recipe, 'recipe'),
                    feedstock_directory=os.path.join(recipe, '{package.name}-feedstock'),
                    no_git_repo=False,
                    variant_config_files=os.path.join(recipe, 'config.yaml'))
    init_obj(args)
    destination = os.path.join(recipe, 'py-test-feedstock')
    assert os.path.isdir(destination)


#TODO: remove the 2 lines below. https://github.com/conda-forge/conda-smithy/issues/650
import pytest
@pytest.mark.xfail
def test_init_multiple_output_matrix(testing_workdir):
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()
    init_obj = cli.Init(subparser)
    recipe = os.path.join(_thisdir, 'recipes', 'multiple_outputs')
    feedstock_dir = os.path.join(testing_workdir, 'multiple-outputs-test-feedstock')
    args = InitArgs(recipe_directory=recipe,
                    feedstock_directory=feedstock_dir,
                    no_git_repo=False,
                    variant_config_files=os.path.join(recipe, 'conda_build_config.yaml'))
    init_obj(args)
    matrix_dir = os.path.join(feedstock_dir, '.ci_support')
    # the matrix should be consolidated among all outputs, as well as the top-level
    # reqs. Only the top-level reqs should have indedependent config files,
    # though - loops within outputs are contained in those top-level configs.
    assert len(os.listdir(matrix_dir)) == 13
    circle_libpng16 = os.path.join(matrix_dir, 'circle_libpng1.6libpq9.5.yaml')
    assert os.path.isfile(circle_libpng16)
    with open(circle_libpng16) as f:
        config = yaml.load(f)
    assert config['libpng'] == ['1.6']
    assert config['libpq'] == ['9.5']
    # this is a zipped key, but it's not used, so it shouldn't show up
    assert 'libtiff' not in config
    assert 'zip_keys' not in config or not any('libtiff' in group for group in config['zip_keys'])
    # this is a variable only for one of the outputs
    assert config['jpeg'] == ['8', '9']
    # this is in conda_build_config.yaml, but is a transitive dependency.  It should
    #     not show up in the final configs.
    assert 'zlib' not in config


def test_regenerate(py_recipe):
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()
    regen_obj = cli.Regenerate(subparser)
    recipe = py_recipe.recipe
    feedstock_dir = os.path.join(_thisdir, 'recipes', 'click-test-feedstock')
    args = RegenerateArgs(feedstock_directory=feedstock_dir,
                          commit=False,
                          variant_config_files=os.path.join(recipe, 'config.yaml'))
    matrix_folder = os.path.join(feedstock_dir, '.ci_support')

    initial_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                             cwd=feedstock_dir).strip()
    try:
        # original rendering was with py27, 36, no target_platform
        assert len(os.listdir(matrix_folder)) == 7
        regen_obj(args)
        # should add 2, as the config.yaml adds in target_platform
        assert len(os.listdir(matrix_folder)) == 9

        # reduce the python matrix and make sure the matrix files reflect the change
        args = RegenerateArgs(feedstock_directory=feedstock_dir,
                              commit=False,
                              variant_config_files=os.path.join(recipe, 'short_config.yaml'))
        matrix_folder = os.path.join(feedstock_dir, '.ci_support')
        # one py ver, no target_platform  (tests that older configs don't stick around)
        regen_obj(args)
        assert len(os.listdir(matrix_folder)) == 4
    finally:
        # reset the test dir for next time
        subprocess.call(['git', 'reset', '--hard', initial_commit],
                        cwd=feedstock_dir)
