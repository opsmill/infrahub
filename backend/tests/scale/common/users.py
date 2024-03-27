import time

import common.stagers
from infrahub_sdk import Config
from locust import User, task

from .config import config
from .protocols import LocustInfrahubClient
from .utils import prepare_node_attributes, random_ascii_string


class InfrahubClientUser(User):
    address: str = ""
    config = Config()
    delete_this_node = None
    update_this_node = None

    def __init__(self, environment):
        super().__init__(environment)

        self.address = environment.custom_options["config"].url
        self.config.api_token = environment.custom_options["config"].api_token
        self.config.timeout = environment.custom_options["config"].client_timeout
        self.custom_options = environment.custom_options

        self.client = LocustInfrahubClient(
            address=self.address, config=self.config, request_event=environment.events.request
        )

    @task
    def crud(self):
        print("--- staging")
        print("--- loading schema")
        if not hasattr(common.stagers, self.custom_options["stager"]):
            raise ValueError(f"Invalid staging function provided: {self.custom_options['stager']}")

        stager = getattr(common.stagers, self.custom_options["stager"])
        if not callable(stager):
            raise ValueError(f"Invalid staging function provided: {self.custom_options['stager']}")

        # Generate extra attributes
        attributes = [
            {"name": f"attr{i}", "kind": "Text", "default_value": "", "optional": True}
            for i in range(self.custom_options["attrs"])
        ]
        # Generate extra relationships
        relationships = [
            {
                "name": f"rel{i}",
                "kind": "Generic",
                "peer": "BuiltinTag",
                "cardinality": "one",
                "identifier": f"builtintag__infranode_{i}",
                "optional": True,
            }
            for i in range(self.custom_options["rels"])
        ]
        common.stagers.load_schema(
            self.client, self.custom_options["schema"], attributes=attributes, relationships=relationships
        )
        time.sleep(5)
        print("--- staging nodes, attributes and relations")
        config.current_stage = "stager"
        stager(
            client=self.client,
            amount=self.custom_options["amount"],
        )
        print("--- 20s cool down period")
        time.sleep(20)

        print("--- starting test")
        config.current_stage = "test"
        extra_attributes = prepare_node_attributes(self.client)
        begin = time.time()
        # Run for at least 5 minutes
        while time.time() < begin + 300:
            objects = self.client.all(kind="InfraNode", limit=50)

            if len(objects) >= 2:
                delete_this_node, update_this_node = objects[0:2]

            obj = self.client.create(kind="InfraNode", data={"name": random_ascii_string(), **extra_attributes})
            obj.save()

            if len(objects) >= 2:
                update_this_node.name.value = random_ascii_string()
                update_this_node.save()

                delete_this_node.delete()

            if "diff" in self.custom_options["stager"]:
                self.client.branch.diff_data("DiffTestBranch")

        # End with a branch merge
        if "diff" in self.custom_options["stager"]:
            self.client.branch.merge("DiffTestBranch")
