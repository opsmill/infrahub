from asyncio import run as aiorun

from infrahub_sdk import InfrahubClient


async def main():
    client = InfrahubClient(address="http://localhost:8000")
    obj = await client.create(
        kind="CoreAccount",
        name="janedoe",
        label="Jane Doe",
        account_type="User",
        password="J0esSecret!",
    )
    await obj.save()
    print(f"New user created with the Id {obj.id}")


if __name__ == "__main__":
    aiorun(main())
