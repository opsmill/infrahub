from infrahub_sdk.transforms import InfrahubTransform


class Transform02(InfrahubTransform):
    query = "my_query"

    def transform(self, data: dict):
        return {str(key).upper(): value for key, value in data.items()}


INFRAHUB_TRANSFORMS = [Transform02]
