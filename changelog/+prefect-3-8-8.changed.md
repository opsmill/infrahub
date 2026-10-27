Upgraded Prefect to `3.8.8` (from `3.8.6`). The first start of the task manager after this upgrade adds an index to the flow run table. On PostgreSQL the index is built without locking the table, but it can take a while on deployments with a long task history. Later starts are unaffected.

A task worker started with `--with-healthcheck` now answers `GET /health` as soon as it starts, before its setup completes. Before, it refused connections until its setup completed.
