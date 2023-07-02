from asyncio import run as aiorun

from infrahub_client import InfrahubClient


async def main():
    client = await InfrahubClient.init(address="http://localhost:8000")
    obj = await client.get(kind="CoreAccount", name__value="admin")
    obj.label.value = "Administrator"
    await obj.save()


if __name__ == "__main__":
    aiorun(main())
