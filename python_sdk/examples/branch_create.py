from asyncio import run as aiorun

from infrahub_sdk import InfrahubClient


async def main():
    client = await InfrahubClient.init(address="http://localhost:8000")
    await client.branch.create(branch_name="new-branch", description="description", data_only=True)
    print("New branch created")


if __name__ == "__main__":
    aiorun(main())
