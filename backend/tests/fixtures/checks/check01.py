from infrahub_sdk_internal.checks import InfrahubCheck


class Check01(InfrahubCheck):
    query = "my_query"

    def validate(self, data):
        self.log_error("Not Valid")


INFRAHUB_CHECKS = [Check01]
