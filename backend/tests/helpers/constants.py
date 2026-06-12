import os

from infrahub_sdk.utils import str_to_bool

INFRAHUB_USE_TEST_CONTAINERS = str_to_bool(os.getenv("INFRAHUB_USE_TEST_CONTAINERS", "true"))
PORT_NATS = 4222
PORT_REDIS = 6379
PORT_CLIENT_RABBITMQ = 5672
PORT_HTTP_RABBITMQ = 15672
PORT_HTTP_NEO4J = 7474
PORT_BOLT_NEO4J = 7687
PORT_MEMGRAPH = 7687
PORT_PREFECT = 4200
NEO4J_COMMUNITY_IMAGE = "neo4j:2025.10.1-community"
NEO4J_ENTERPRISE_IMAGE = "neo4j:2025.10.1-enterprise"
NEO4J_IMAGE = os.getenv("NEO4J_DOCKER_IMAGE", NEO4J_ENTERPRISE_IMAGE)

# Upper bound in seconds when polling for Prefect events and their side effects
# (event persistence, triggered automations, computed attribute rendering).
PREFECT_EVENT_WAIT_SECONDS = 60

# The crash-zombie-flows automation crashes flow runs whose heartbeats stop arriving within
# a 90 second window, and the flow engine always emits an initial heartbeat when a flow
# starts regardless of the configured frequency. The frequency must therefore stay well
# below that window (production uses 30s); stretching it to "disable" heartbeats only
# silences the follow-up beats and gets healthy long-running flows crashed.
PREFECT_FLOW_HEARTBEAT_FREQUENCY_SECONDS = "30"

# The test Prefect servers (ephemeral subprocess and the prefect container fixture) run
# every background service in-process against a single SQLite database. SQLite serializes
# writers, so the periodic services contend with the API and with trigger/event processing;
# under parallel test load API requests and event delivery can block for minutes and time
# the suites out. Disable everything the tests do not rely on. Triggers (automations power
# computed attributes and action rules), the event persister (events are queried by tests)
# and the task run recorder (flow/task run state) stay enabled.
PREFECT_SERVER_NONESSENTIAL_SERVICE_ENV_VARS: dict[str, str] = {
    # Loop/perpetual services: schedule cron deployment runs, mark runs late, monitor
    # worker/work-queue health, expire pauses and leases, clean up cancellations.
    "PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED": "false",
    "PREFECT_SERVER_SERVICES_FOREMAN_ENABLED": "false",
    "PREFECT_SERVER_SERVICES_LATE_RUNS_ENABLED": "false",
    "PREFECT_SERVER_SERVICES_PAUSE_EXPIRATIONS_ENABLED": "false",
    "PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED": "false",
    "PREFECT_SERVER_SERVICES_REPOSSESSOR_ENABLED": "false",
    "PREFECT_SERVER_SERVICES_CLEANUP_RECONCILER_ENABLED": "false",
    # Periodic event retention/vacuum passes; pointless on short-lived test databases.
    "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": "[]",
    # Telemetry heartbeat to an external endpoint.
    "PREFECT_SERVER_ANALYTICS_ENABLED": "false",
}
