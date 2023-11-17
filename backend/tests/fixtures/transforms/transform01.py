from infrahub_sdk.transforms import InfrahubTransform


class Transform01(InfrahubTransform):
    query = "my_query"
    url = "transform01"

    def transform(self, data: dict):
        return {str(key).upper(): value for key, value in data.items()}


INFRAHUB_TRANSFORMS = [Transform01]
