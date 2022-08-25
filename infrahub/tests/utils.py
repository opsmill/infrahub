import os
from distutils.dir_util import copy_tree


def get_fixtures_dir():
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "..", "..", "tests", "fixtures")
    return fixtures_dir


def copy_project_to_tmp_dir(project_name):
    """Function used to copy data to isolated file system."""
    fixtures_dir = get_fixtures_dir()
    copy_tree(os.path.join(fixtures_dir, project_name), "./")
