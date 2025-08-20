from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class CarSpecMarkdown(InfrahubTransform):
    query = "person_with_cars"
    timeout = 10

    async def transform(self, data: dict[str, Any]) -> str:
        markdown = """
        ## Car Specification

        **blue** Sedan
        Make: **Toyota**
        Model: **Camry**
        """
        return markdown
