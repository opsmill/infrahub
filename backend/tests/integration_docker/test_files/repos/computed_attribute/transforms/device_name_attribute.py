from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class DeviceNameAttribute(InfrahubTransform):
    query = "device_name_attribute"

    async def transform(self, data: dict[str, Any]) -> str:
        device = data["InfraDevice"]["edges"][0]["node"]
        device_type = device["device_type"]["value"]
        device_instance = device["instance"]["value"]
        site = device["site"]["node"]
        site_name = site["name"]["value"]
        country_name = site["parent"]["node"]["name"]["value"]

        rendered_name = f"{country_name}-{site_name}-{device_type}-{device_instance}"
        return rendered_name.lower()
