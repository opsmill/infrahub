bind = "0.0.0.0:8000"
timeout = 90
workers = 4
worker_class = "infrahub.serve.worker.InfrahubUvicorn"


# Validate Infrahub settings in the master before workers fork.
# This replaces `preload_app = True`, which we can't enable because `infrahub.worker.WORKER_IDENTITY` is a
# module-scope UUID: preloading would make every forked worker share one identity and collide when they each try
# to declare the exclusive RabbitMQ queue.
def on_starting(server: object) -> None:  # noqa: ARG001
    from infrahub import config

    config.SETTINGS.initialize_and_exit()
