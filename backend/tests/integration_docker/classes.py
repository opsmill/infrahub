import os

from infrahub_sdk.testing.docker import TestInfrahubDockerClient


class TestDockerIntegration(TestInfrahubDockerClient):
    """
    Perform a test against an Infrahub image. Typically, a prior `dev.build` should be executed before running
    a test inheriting from this class, in order to build the local image.
    """

    @staticmethod
    def infrahub_version() -> str:
        return os.getenv("INFRAHUB_TESTING_IMAGE_TAG", "local")
