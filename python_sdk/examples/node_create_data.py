from asyncio import run as aiorun

from infrahub_sdk import InfrahubClient


async def main():
    client = InfrahubClient(address="http://localhost:8000")
    data = {
        "name": "johndoe",
        "label": "John Doe",
        "type": "User",
        "password": "J0esSecret!",
    }
    obj = await client.create(kind="CoreAccount", data=data)
    await obj.save()
    print(f"New user created with the Id {obj.id}")


if __name__ == "__main__":
    aiorun(main())
