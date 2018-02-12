import os
import conda_smithy.configure_feedstock as cnfgr_fdstk

import pytest


def test_noarch_skips_appveyor(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_appveyor(jinja_env=jinja_env,
                                forge_config=noarch_recipe.config,
                                forge_dir=noarch_recipe.recipe)
    # this configuration should be skipped
    assert not noarch_recipe.config['appveyor']['enabled']
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    assert not os.path.isdir(os.path.join(noarch_recipe.recipe, '.ci_support'))


def test_noarch_skips_travis(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_travis(jinja_env=jinja_env,
                              forge_config=noarch_recipe.config,
                              forge_dir=noarch_recipe.recipe)
    # this configuration should be skipped
    assert not noarch_recipe.config['travis']['enabled']
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    assert not os.path.isdir(os.path.join(noarch_recipe.recipe, '.ci_support'))


def test_noarch_runs_on_circle(noarch_recipe, jinja_env):
    cnfgr_fdstk.render_circle(jinja_env=jinja_env,
                              forge_config=noarch_recipe.config,
                              forge_dir=noarch_recipe.recipe)
    # this configuration should be run
    assert noarch_recipe.config['circle']['enabled']
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(noarch_recipe.recipe, '.ci_support')
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 1


def test_r_skips_appveyor(r_recipe, jinja_env):
    cnfgr_fdstk.render_appveyor(jinja_env=jinja_env,
                                forge_config=r_recipe.config,
                                forge_dir=r_recipe.recipe)
    # this configuration should be skipped
    assert not r_recipe.config['appveyor']['enabled']
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    assert not os.path.isdir(os.path.join(r_recipe.recipe, '.ci_support'))


def test_r_matrix_travis(r_recipe, jinja_env):
    cnfgr_fdstk.render_travis(jinja_env=jinja_env,
                              forge_config=r_recipe.config,
                              forge_dir=r_recipe.recipe)
    # this configuration should be run
    assert r_recipe.config['travis']['enabled']
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(r_recipe.recipe, '.ci_support')
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_r_matrix_on_circle(r_recipe, jinja_env):
    cnfgr_fdstk.render_circle(jinja_env=jinja_env,
                              forge_config=r_recipe.config,
                              forge_dir=r_recipe.recipe)
    # this configuration should be run
    assert r_recipe.config['circle']['enabled']
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(r_recipe.recipe, '.ci_support')
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_py_matrix_appveyor(py_recipe, jinja_env):
    cnfgr_fdstk.render_appveyor(jinja_env=jinja_env,
                                forge_config=py_recipe.config,
                                forge_dir=py_recipe.recipe)
    # this configuration should be skipped
    assert py_recipe.config['appveyor']['enabled']
    matrix_dir = os.path.join(py_recipe.recipe, '.ci_support')
    assert os.path.isdir(matrix_dir)
    # 2 python versions, 2 target_platforms
    assert len(os.listdir(matrix_dir)) == 4


def test_py_matrix_travis(py_recipe, jinja_env):
    cnfgr_fdstk.render_travis(jinja_env=jinja_env,
                              forge_config=py_recipe.config,
                              forge_dir=py_recipe.recipe)
    # this configuration should be run
    assert py_recipe.config['travis']['enabled']
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(py_recipe.recipe, '.ci_support')
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_py_matrix_on_circle(py_recipe, jinja_env):
    cnfgr_fdstk.render_circle(jinja_env=jinja_env,
                              forge_config=py_recipe.config,
                              forge_dir=py_recipe.recipe)
    # this configuration should be run
    assert py_recipe.config['circle']['enabled']
    # no appveyor.yaml should have been written.  Nothing else, either, since we only ran
    #     appveyor render.  No matrix dir should exist.
    matrix_dir = os.path.join(py_recipe.recipe, '.ci_support')
    assert os.path.isdir(matrix_dir)
    # single matrix entry - readme is generated later in main function
    assert len(os.listdir(matrix_dir)) == 2


def test_circle_with_yum_reqs(py_recipe, jinja_env):
    with open(os.path.join(py_recipe.recipe, 'recipe', 'yum_requirements.txt'), 'w') as f:
        f.write('nano\n')
    cnfgr_fdstk.render_circle(jinja_env=jinja_env,
                              forge_config=py_recipe.config,
                              forge_dir=py_recipe.recipe)


def test_circle_with_empty_yum_reqs_raises(py_recipe, jinja_env):
    with open(os.path.join(py_recipe.recipe, 'recipe', 'yum_requirements.txt'), 'w') as f:
        f.write('# effectively empty')
    with pytest.raises(ValueError):
        cnfgr_fdstk.render_circle(jinja_env=jinja_env,
                                  forge_config=py_recipe.config,
                                  forge_dir=py_recipe.recipe)
