from infrahub_sdk.checks import InfrahubCheck


class Check01(InfrahubCheck):
    query = "my_query"

    def validate(self):
        self.log_error("Not Valid")


INFRAHUB_CHECKS = [Check01]
