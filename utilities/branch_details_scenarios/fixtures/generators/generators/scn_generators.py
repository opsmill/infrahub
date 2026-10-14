# noqa: INP001
from infrahub_sdk.generator import InfrahubGenerator


class OkGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        device = data["InfraDevice"]["edges"][0]["node"]
        self.logger.info(f"scn-gen-ok looked at {device['name']['value']}")


class FailingGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        # Raises KeyError on purpose, so every run of this definition fails.
        self.logger.info(data["scn_missing_key"])
