from prometheus_client import Histogram

METRIC_PREFIX = "infrahub_graphql"

SCHEMA_GENERATE_GRAPHQL_METRICS = Histogram(
    f"{METRIC_PREFIX}_generate_schema",
    "Time to generate the GraphQL Schema",
    labelnames=["branch"],
    buckets=[0.0005, 0.25, 0.5, 1, 5],
)

GRAPHQL_DURATION_METRICS = Histogram(
    f"{METRIC_PREFIX}_duration_seconds",
    "GraphQL query duration, in seconds",
    labelnames=["type", "operation", "branch", "name", "query_id"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.5, 1, 5, 10, 60],
)
GRAPHQL_RESPONSE_SIZE_METRICS = Histogram(
    f"{METRIC_PREFIX}_response_size_bytes",
    "GraphQL query response size, in bytes",
    labelnames=["type", "operation", "branch", "name", "query_id"],
    buckets=[500, 1000, 5000, 10000, 100000, 1000000],
)
GRAPHQL_QUERY_DEPTH_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_depth",
    "GraphQL query depth",
    labelnames=["type", "operation", "branch", "name", "query_id"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 25, 50, 100],
)
GRAPHQL_QUERY_HEIGHT_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_height",
    "GraphQL query height",
    labelnames=["type", "operation", "branch", "name", "query_id"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 25, 50, 100],
)
GRAPHQL_QUERY_VARS_METRICS = Histogram(
    f"{METRIC_PREFIX}_variables",
    "GraphQL query number of variables",
    labelnames=["type", "operation", "branch", "name", "query_id"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 25, 50, 100],
)
GRAPHQL_QUERY_ERRORS_METRICS = Histogram(
    f"{METRIC_PREFIX}_errors",
    "GraphQL query number of errors",
    labelnames=["type", "operation", "branch", "name", "query_id"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 25, 50, 100],
)
GRAPHQL_QUERY_OBJECTS_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_objects",
    "GraphQL number of objects in the query",
    labelnames=["type", "operation", "branch", "name", "query_id"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 25, 50, 100],
)
GRAPHQL_TOP_LEVEL_QUERIES_METRICS = Histogram(
    f"{METRIC_PREFIX}_top_level_queries",
    "GraphQL number of top level queries",
    labelnames=["type", "operation", "branch", "name", "query_id"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 25, 50, 100],
)
