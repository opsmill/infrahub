from asyncio import run as aiorun

from infrahub_sdk import InfrahubClient


async def main():
    client = InfrahubClient(address="http://localhost:8000")
    await client.branch.create(branch_name="new-branch", description="description", sync_with_git=False)
    print("New branch created")


if __name__ == "__main__":
    aiorun(main())
