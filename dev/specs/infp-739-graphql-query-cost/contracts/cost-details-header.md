# HTTP contract: the cost-details header

**Feature**: INFP-739 | **Schema of the content**: [cost-details.schema.json](cost-details.schema.json)

## Request

| Header | Value | Effect |
| --- | --- | --- |
| `X-Infrahub-Query-Cost` | `details` (compared without case) | The response carries `extensions.query_cost`. |
| `X-Infrahub-Query-Cost` | any other value | Ignored. |
| (absent) | | The request runs as it does today. |

Endpoints that read the header:

- `POST /graphql` and `POST /graphql/{branch}`
- `GET /api/query/{query_id}` and `POST /api/query/{query_id}`

The header is ignored on WebSocket subscriptions and on operations that contain a mutation (FR-015).

## Response

`/graphql`, with the header:

```json
{
  "data": { "...": "..." },
  "errors": [ "only when the query has errors" ],
  "extensions": { "query_cost": { "...": "see cost-details.schema.json" } }
}
```

`/api/query/{query_id}`, with the header:

```json
{
  "data": { "...": "..." },
  "extensions": { "query_cost": { "...": "see cost-details.schema.json" } }
}
```

Without the header, both responses are the same as today: no `extensions` key.

## Counting rules

- `resolver_calls`: one for each time the field's resolver ran, including a retry after a transient database error.
- `nodes`: nodes the field returned, summed over every parent node.
- `database_rows`: rows the database returned to queries that ran while the field's resolver was running. A batch of cardinality-one peers that serves several fields with the same selection is counted for the field whose resolver started the batch.
- Queries that the counted first step ran are reported under `estimate_queries`, not under any field.
