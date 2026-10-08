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
- Queries that the counted first step ran are reported under `estimate_queries`, not under any field. Queries that ran while no field was being resolved are reported under `unattributed`.
- Counting starts when the request handler has read the operation and found no mutation. Queries that run before that point are not reported: authentication, loading the account's permissions and, on `/api/query`, reading the stored query.
- The first step is always counted on these endpoints, because a request runs with its variable values (`estimate_mode = counted_first_step`), unless no estimate can be computed (see below).
- Fields with the same path, for example a field selected directly and through a fragment, have one entry. Root fields that do not map to a schema kind have no entry.

## When no estimate can be computed

A request with the header returns the same `data` and `errors` as the same request without it. When the estimate cannot be computed, the cost details carry no estimate:

- `estimate_mode` is `statistics_only` and `statistics` is `null`
- every recorded field has `reason = "no statistics"`
- `estimate_queries` lists the counting queries that ran before the failure

This happens in these cases:

- The variables do not match their declared types. No field runs, so `fields` is empty, and `errors` holds the graphql-core coercion error, as without the header.
- The `offset` or `limit` of a top-level field is negative. `errors` holds the error of that field, as without the header.
- Reading the statistics from the cache, or a counting query, fails. The server logs the failure with its traceback.
