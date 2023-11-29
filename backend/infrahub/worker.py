import uuid
from enum import Enum

WORKER_IDENTITY = str(uuid.uuid4())


class WorkerType(str, Enum):
    API = "api"
    GIT_AGENT = "git_agant"
