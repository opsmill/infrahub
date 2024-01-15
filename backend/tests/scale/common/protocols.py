import time

from infrahub_sdk import Config, InfrahubClientSync


class LocustInfrahubClient(InfrahubClientSync):
    "Locust protocol for Python Infrahub SDK client"

    def __init__(self, address: str, config: Config, request_event):
        super().__init__(address=address, config=config)
        self._request_event = request_event

    def execute_graphql(self, *args, **kwargs):
        request_meta = {
            "request_type": "InfrahubClient",
            "name": kwargs.get("tracker", "graphql_query"),
            "start_time": time.time(),
            "response_length": 0,
            "response": None,
            "context": {},
            "exception": None,
        }
        start_perf_counter = time.perf_counter()
        try:
            request_meta["response"] = super().execute_graphql(*args, **kwargs)
        except Exception as e:
            request_meta["exception"] = e
        request_meta["response_time"] = (time.perf_counter() - start_perf_counter) * 1000
        self._request_event.fire(**request_meta)
        return request_meta["response"]
