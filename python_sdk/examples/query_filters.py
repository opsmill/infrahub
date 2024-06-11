from asyncio import run as aiorun

from rich import print as rprint

from infrahub_sdk import InfrahubClient


async def main():
    client = InfrahubClient(address="http://localhost:8000")
    accounts = await client.filters(kind="CoreAccount")
    rprint(accounts)


if __name__ == "__main__":
    aiorun(main())
