from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class Foo(InfrahubTransform):
    query = "GetPythonDevice"
    timeout = 10

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"rendered": data}
