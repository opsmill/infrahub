import json
import os
import sys
from abc import abstractmethod

import httpx
from git import Repo

VARIABLE_TO_IMPORT = "INFRAHUB_CHECKS"


class InfrahubCheck:

    query = None

    def __init__(self, branch=None, root_directory=None, output=None, server_url=None, rebase=True):

        self.data = None
        self.git = None

        self.logs = []
        self.passed = None

        self.output = output

        self.branch = branch
        self.rebase = rebase

        self.server_url = server_url or os.environ.get("INFRAHUB_URL", "http://127.0.0.1:8000")
        self.root_directory = root_directory or os.getcwd()

        # TODO VALIDATE That QUERY is defined

    def log_error(self, message, object_id=None, object_type=None):

        log_message = {"level": "ERROR", "message": message, "branch": self.branch_name}
        if object_id:
            log_message["object_id"] = object_id
        if object_type:
            log_message["object_type"] = object_type
        self.logs.append(log_message)

        if self.output == "stdout":
            print(json.dumps(log_message))

    def log_info(self, message, object_id=None, object_type=None):

        log_message = {"level": "INFO", "message": message, "branch": self.branch_name}
        if object_id:
            log_message["object_id"] = object_id
        if object_type:
            log_message["object_type"] = object_type

        self.logs.append(log_message)

        if self.output == "stdout":
            print(json.dumps(log_message))

    @property
    def branch_name(self):
        """Return the name of the current git branch."""

        if self.branch:
            return self.branch

        if not self.git:
            self.git = Repo(self.root_directory)
            self.branch = str(self.git.active_branch)

        return self.branch

    @abstractmethod
    def validate(self):
        pass

    def collect_data(self):
        params = {"branch": self.branch_name, "rebase": self.rebase}
        resp = httpx.get(f"{self.server_url}/query/{self.query}", params=params)
        resp.raise_for_status()
        data = resp.json()
        self.data = data

    def run(self):
        self.collect_data()
        self.validate()

        nbr_errors = len([log for log in self.logs if log["level"] == "ERROR"])

        self.passed = True if nbr_errors == 0 else False

        if not self.passed and self.output == "stdout":
            sys.exit(1)
        elif self.passed:
            self.log_info("check succesfully completed")

        return self.passed
