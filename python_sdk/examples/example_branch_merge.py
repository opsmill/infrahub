from asyncio import run as aiorun

from infrahub_client import InfrahubClient


async def main():
    client = await InfrahubClient.init(address="http://localhost:8000")
    await client.branch.merge(branch_name="new_branch")

if __name__ == "__main__":
    aiorun(main())
