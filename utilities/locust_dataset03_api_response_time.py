from locust import TaskSet, task, HttpUser


# class InfrahubDataset03(TaskSet):

# class InfrahubDataset03(TaskSet):
#     @task
#     def get_device_names(self):
#         query = """
#         query {
#             device {
#                 name {
#                     value
#                 }
#             }
#         }
#         """
#         data = {"query": query}
#         self.client.post("/graphql", json=data)

#     @task(2)
#     def get_one_device(self):
#         query = """
#         query {
#             device(name__value: "ord1-edge1"){
#                 name {
#                     value
#                 }
#                 interfaces {
#                     name {
#                         value
#                     }
#                 }
#             }
#         }
#         """
#         data = {"query": query}
#         self.client.post("/graphql", json=data)


class InfrahubUser(HttpUser):
    host = "http://localhost:8000"
    # tasks = [InfrahubDataset03]

    @task
    def query_device_names(self):
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
    def query_one_device(self):
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
