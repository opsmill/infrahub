bind = "0.0.0.0:8000"
timeout = 90
workers = 4
worker_class = "infrahub.serve.worker.InfrahubUvicorn"
# Import the app in the master before forking workers
preload_app = True
