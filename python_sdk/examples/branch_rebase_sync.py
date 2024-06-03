from infrahub_sdk import InfrahubClientSync


def main():
    client = InfrahubClientSync(address="http://localhost:8000")
    client.branch.rebase(branch_name="new-branch")


if __name__ == "__main__":
    main()
