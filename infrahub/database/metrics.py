from prometheus_client import Histogram

METRIC_PREFIX = "infrahub_db"

QUERY_READ_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_read_execution_seconds", "Execution time to read information from the database"
)
QUERY_WRITE_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_write_execution_seconds", "Execution time to write information from the database"
)
