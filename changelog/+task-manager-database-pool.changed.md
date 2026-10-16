Changed the task manager to keep its database connections open between requests instead of reconnecting under load, which reduces database CPU and speeds up background tasks on smaller deployments.
