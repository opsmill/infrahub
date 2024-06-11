from asyncio import run as aiorun

from infrahub_sdk import InfrahubClient


async def main():
    client = InfrahubClient(address="http://localhost:8000")
    obj = await client.get(kind="CoreAccount", name__value="johndoe")
    await obj.delete()


if __name__ == "__main__":
    aiorun(main())
