from asyncio import run as aiorun

from infrahub_sdk import InfrahubClient


async def main():
    client = InfrahubClient(address="http://localhost:8000")
    obj = await client.get(kind="CoreAccount", name__value="admin")
    obj.label.value = "Administrator"
    await obj.save()


if __name__ == "__main__":
    aiorun(main())
