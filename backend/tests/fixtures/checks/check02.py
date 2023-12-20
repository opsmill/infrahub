from infrahub_sdk.checks import InfrahubCheck


class Check02(InfrahubCheck):
    """Non valid Check for testing.
    The query is missing."""

    def validate(self):
        self.log_error("Not Valid")


INFRAHUB_CHECKS = [Check02]
