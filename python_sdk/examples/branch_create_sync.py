from infrahub_sdk import InfrahubClientSync


def main():
    client = InfrahubClientSync.init(address="http://localhost:8000")
    client.branch.create(branch_name="new-branch2", description="description", data_only=True)
    print("New branch created")


if __name__ == "__main__":
    main()
