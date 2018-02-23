import argparse
import collections
import os
import subprocess
import yaml
import shutil

from conda_smithy import cli

_thisdir = os.path.abspath(os.path.dirname(__file__))

InitArgs = collections.namedtuple('ArgsObject', ('recipe_directory',
                                                 'feedstock_directory'))

RegenerateArgs = collections.namedtuple('ArgsObject', ('commit',
                                                       'feedstock_directory',
                                                       'no_check_uptodate'))


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
                    feedstock_directory=os.path.join(recipe, '{package.name}-feedstock'))
    init_obj(args)
    destination = os.path.join(recipe, 'py-test-feedstock')
    assert os.path.isdir(destination)


def test_init_multiple_output_matrix(testing_workdir):
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()
    init_obj = cli.Init(subparser)
    regen_obj = cli.Regenerate(subparser)
    recipe = os.path.join(_thisdir, 'recipes', 'multiple_outputs')
    feedstock_dir = os.path.join(testing_workdir, 'multiple-outputs-test-feedstock')
    args = InitArgs(recipe_directory=recipe,
                    feedstock_directory=feedstock_dir)
    init_obj(args)
    # Ignore conda-forge-pinning for this test, as the test relies on conda-forge-pinning
    # not being present
    with open(os.path.join(feedstock_dir, "conda-forge.yml"), "w") as f:
        f.write("exclusive_config_file: recipe/conda_build_config.yaml")
    args = RegenerateArgs(feedstock_directory=feedstock_dir,
                          commit=False,
                          no_check_uptodate=True)
    regen_obj(args)
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


def test_regenerate(py_recipe, testing_workdir):
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()
    regen_obj = cli.Regenerate(subparser)
    recipe = py_recipe.recipe
    feedstock_dir = os.path.join(_thisdir, 'recipes', 'click-test-feedstock')
    dest_dir = os.path.join(testing_workdir, 'click-test-feedstock')
    shutil.copytree(feedstock_dir, dest_dir)
    subprocess.call('git init'.split(), cwd=dest_dir)
    subprocess.call('git add *'.split(), cwd=dest_dir)
    subprocess.call('git commit -m "init"'.split(), cwd=dest_dir)
    matrix_folder = os.path.join(dest_dir, '.ci_support')

    # original rendering was with py27, 36, no target_platform
    assert len(os.listdir(matrix_folder)) == 7

    dest_file = os.path.join(dest_dir, 'recipe', 'conda_build_config.yaml')
    args = RegenerateArgs(feedstock_directory=dest_dir,
                          commit=False,
                          no_check_uptodate=True)

    # Ignore conda-forge-pinning for this test, as the test relies on conda-forge-pinning
    # not being present
    with open(os.path.join(dest_dir, "conda-forge.yml"), "w") as f:
        f.write("exclusive_config_file: {}".format(os.path.join(recipe, 'config.yaml')))
    regen_obj(args)

    # should add 2, as the config.yaml adds in target_platform
    assert len(os.listdir(matrix_folder)) == 9

    # reduce the python matrix and make sure the matrix files reflect the change
    with open(os.path.join(dest_dir, "conda-forge.yml"), "w") as f:
        f.write("exclusive_config_file: {}".format(os.path.join(recipe, 'short_config.yaml')))
    regen_obj(args)

    # one py ver, no target_platform  (tests that older configs don't stick around)
    assert len(os.listdir(matrix_folder)) == 4
