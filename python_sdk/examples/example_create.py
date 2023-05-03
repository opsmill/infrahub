from asyncio import run as aiorun

from infrahub_client import InfrahubClient


async def main():
    client = await InfrahubClient.init(address="http://localhost:8000")
    obj = await client.create(kind="Account", data={"name": "johndoe", "label": "John Doe", "type": "User"})
    await obj.save()
    print(f"New user created with the Id {obj.id}")

if __name__ == "__main__":
    aiorun(main())
