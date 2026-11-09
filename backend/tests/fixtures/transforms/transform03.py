from infrahub_sdk.transforms import InfrahubTransform


class Transform03(InfrahubTransform):
    """Transform without a payload, as happens when conditional logic returns early."""

    query = "my_query"
    url = "transform03"

    def transform(self, data: dict) -> None:
        return None


INFRAHUB_TRANSFORMS = [Transform03]
