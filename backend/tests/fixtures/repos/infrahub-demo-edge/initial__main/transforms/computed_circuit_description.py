from infrahub_sdk.transforms import InfrahubTransform


class ComputedCircuitDescription(InfrahubTransform):
    query = "computed_circuit_description"
    url = "computed_circuit_description"

    async def transform(self, data):
        circuit_dict: dict = data["InfraCircuit"]["edges"][0]["node"]

        # If it's a backbone we compute a nice view
        if circuit_dict["role"]["value"] == "backbone":
            detailed_endpoints: list[str] = []

            for endpoint in circuit_dict["endpoints"]["edges"]:
                connected_endpoint: dict = endpoint["node"]["connected_endpoint"][
                    "node"
                ]
                detailed_endpoints.append(
                    f'{connected_endpoint["device"]["node"]["name"]["value"]}::{connected_endpoint["name"]["value"]}'
                )

            return f' < {circuit_dict["circuit_id"]["value"]} > '.join(
                detailed_endpoints
            )

        return f'This {circuit_dict["role"]["value"]} circuit is provided by {circuit_dict["provider"]["node"]["name"]["value"]}'
