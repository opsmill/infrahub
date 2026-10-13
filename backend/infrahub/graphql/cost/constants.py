QUERY_COST_HEADER = "X-Infrahub-Query-Cost"
QUERY_COST_HEADER_VALUE = "details"

STATISTICS_POINTER_KEY = "graphql_cost:statistics:current"
STATISTICS_KIND_KEY_TEMPLATE = "graphql_cost:statistics:v{version}:kind:{kind}"

TOP_NODES_LIMIT = 20

NO_STATISTICS_REASON = "no statistics"

# Angle brackets cannot appear in a GraphQL name, so no path built from response keys equals this value.
ESTIMATE_FIELD_PATH = "<estimate>"
