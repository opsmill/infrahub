import uuid

import pkg_resources

WORKER_IDENTITY = str(uuid.uuid4())

__version__ = pkg_resources.get_distribution("infrahub").version
