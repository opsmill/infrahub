from rich import print as rprint

from infrahub_sdk import InfrahubClientSync


def main():
    client = InfrahubClientSync(address="http://localhost:8000")
    branches = client.branch.all()
    rprint(branches)


if __name__ == "__main__":
    main()
