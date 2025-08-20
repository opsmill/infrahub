from typing import Any

from infrahub_sdk.transforms import InfrahubTransform

from .model import Pitch


class TShirtPitch(InfrahubTransform):
    query = "tshirt_colors"

    async def transform(self, data: dict[str, Any]) -> str:
        pitch = Pitch.from_data(data=data)
        return pitch.render()
