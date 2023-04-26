from infrahub_client import InfrahubClientSync


def main():
    client = InfrahubClientSync.init(address="http://localhost:8000")
    obj = client.create(kind="Account", data={"name": "janedoe", "label": "Jane Doe", "type": "User"})
    obj.save()
    print(f"New user created with the Id {obj.id}")


if __name__ == "__main__":
    main()
