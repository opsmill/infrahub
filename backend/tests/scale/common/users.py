from infrahub_sdk import Config
from locust import HttpUser, User, task

from .config import Config as ScaleTestConfig
from .protocols import LocustInfrahubClient
from .utils import random_ascii_string

config = ScaleTestConfig()


class InfrahubUIUser(HttpUser):
    host = config.url

    def on_start(self):
        self.client.post("/api/auth/login", data={"username": config.username, "password": config.password})

    @task
    def crud(self):
        self.client.get("/objects/InfraNode")


class InfrahubClientUser(User):
    address = config.url
    config = Config(api_token=config.api_token, timeout=config.client_timeout)
    delete_this_node = None
    update_this_node = None

    def __init__(self, environment):
        super().__init__(environment)
        self.client = LocustInfrahubClient(
            address=self.address, config=self.config, request_event=environment.events.request
        )

    @task
    def crud(self):
        objects = self.client.all(kind="InfraNode", limit=50)

        if len(objects) >= 2:
            delete_this_node, update_this_node = objects[0:2]

        obj = self.client.create(kind="InfraNode", data={"name": random_ascii_string()})
        obj.save()

        if len(objects) >= 2:
            update_this_node.name.value = random_ascii_string()
            update_this_node.save()

            delete_this_node.delete()
