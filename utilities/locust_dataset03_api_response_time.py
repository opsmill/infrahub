from locust import HttpUser, task


class InfrahubUser(HttpUser):
    host = "http://localhost:8000"
    # tasks = [InfrahubDataset03]

    @task
    def query_device_names(self) -> None:
        query = """
        query {
            device {
                name {
                    value
                }
            }
        }
        """
        data = {"query": query}
        self.client.post("/graphql", json=data, name="query_device_names")

    @task
    def query_one_device(self) -> None:
        query = """
        query {
            device(name__value: "ord1-edge1"){
                name {
                    value
                }
                interfaces {
                    name {
                        value
                    }
                }
            }
        }
        """
        data = {"query": query}
        self.client.post("/graphql", json=data, name="query_one_device")
