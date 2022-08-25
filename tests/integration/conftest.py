import pytest
from fastapi.testclient import TestClient

from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.utils import delete_all_nodes
from infrahub.main import app
from infrahub.test_data import dataset01 as ds01


@pytest.fixture(scope="module")
def init_db():
    delete_all_nodes()
    first_time_initialization()
    initialization()


@pytest.fixture(scope="module")
def client(init_db):
    # api_client = TestClient(app)
    return TestClient(app)


@pytest.fixture(scope="module")
def dataset01(init_db):

    ds01.load_data()
