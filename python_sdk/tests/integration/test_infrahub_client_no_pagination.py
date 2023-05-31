from .test_infrahub_client import TestInfrahubClient as BaseTestInfrahubClient

# pylint: disable=unused-argument


class TestNoPaginationInfrahubClient(BaseTestInfrahubClient):
    pagination: bool = False
