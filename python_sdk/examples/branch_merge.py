from asyncio import run as aiorun

from infrahub_sdk import InfrahubClient


async def main():
    client = InfrahubClient(address="http://localhost:8000")
    await client.branch.merge(branch_name="new-branch")


if __name__ == "__main__":
    aiorun(main())
