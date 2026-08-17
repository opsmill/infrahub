# Webhook delivery: UI test plan

High-level manual plan to validate webhook delivery operability from the UI. Covers a succeeding
delivery, the failing-delivery retry cycle, the operator retry/cancel actions, and the captured
request/response/error now shown on a delivery.

## Setup

| Item | Value |
|------|-------|
| Stack | Running dev stack with the task-manager (Prefect) worker active |
| Target | An HTTP endpoint you control, able to return 200 and 500 on demand |
| Success webhook | Standard webhook with a shared key, pointing at the 200 path, firing on a node event |
| Failure webhook | Custom webhook pointing at the 500 path, firing on a node event |
| Where deliveries appear | Tasks page, the webhook's Tasks tab, and the object's Tasks tab. Each delivery is a `webhook-send` run |

Retry cadence: four attempts (the initial send plus three retries), about two minutes apart.

## Interfaces

A delivery is a `webhook-send` run. It can be reached, and therefore tested, four ways.

| Interface | Where | Exposes |
|-----------|-------|---------|
| UI, Tasks page | `/tasks` | List of runs; each delivery is a `webhook-send` row with a state badge |
| UI, Task detail panel | `/tasks/<run-id>` | State, per-attempt logs, request / response / error, and the Retry and Cancel actions |
| UI, webhook Tasks tab | Webhook object detail, Tasks tab | The deliveries related to that webhook |
| GraphQL | `/graphql` | `InfrahubTask` query, `InfrahubTaskRetry` and `InfrahubTaskCancel` mutations |
| Python SDK | `client.task` | Read runs, plus `retry` and `cancel` actions |

GraphQL entry points:

```graphql
# Read a delivery and its capture. A webhook_send run resolves to WebhookDeliveryTask.
query {
  InfrahubTask(ids: ["<run-id>"]) {
    edges {
      node {
        state
        conclusion
        ... on WebhookDeliveryTask {
          available_actions { action available unavailability_reason }
          http_request { url headers }
          http_response { status_code body latency_ms }
          error { status_class message remediation }
        }
        logs { edges { node { severity message } } }
      }
    }
  }
}

# Operator actions.
mutation { InfrahubTaskRetry(data: { id: "<run-id>" }) { ok task { id } } }
mutation { InfrahubTaskCancel(data: { id: "<run-id>" }) { ok task { id } } }
```

Filter to one webhook's deliveries with `InfrahubTask(related_node__ids: ["<webhook-id>"])`.

Python SDK, via `client.task`: `all`, `filter`, and `get` (pass `include_actions=True`), plus `count`
and `wait_for_completion`, read a run's state, conclusion, logs, related nodes, and action
eligibility (`available_actions`, `can_retry`, `can_cancel`). `retry(id)` returns a new run id and
`cancel(id)` returns an ok flag. The capture fields (`http_request`, `http_response`, `error`) are not
exposed in the SDK; use GraphQL or the UI to inspect those.

## Scenarios

| # | Scenario | Trigger | Expected in the UI |
|---|----------|---------|--------------------|
| 1 | Successful delivery | Fire the success webhook's event | A `webhook-send` task appears, settles COMPLETED. The target receives the signed payload |
| 2 | Automatic retries then failure | Fire the failure webhook's event (target returns 500) | The delivery stays in progress across four attempts about two minutes apart, then settles FAILED |
| 3 | Plain-language failure reason | Open the failed delivery from scenario 2 | Logs show a classified reason and a remediation hint (for the 500 target, `HTTP_SERVER_ERROR`). No stack trace |
| 4 | Per-attempt request log | Open any delivery, read its logs | Each attempt logs its number (n of 4), the target URL, the request headers with secret values masked, and the payload |
| 5 | Action availability | Compare an in-progress delivery with a settled one | In progress: Cancel available, Retry unavailable with a reason. Settled: Retry available, Cancel unavailable with a reason |
| 6 | Retry after fixing the target | Let a delivery fail, repoint the webhook at the 200 path, Retry from the task detail | A new `webhook-send` run appears, resends the original payload, and succeeds. The original failed delivery is unchanged |
| 7 | Outcome reporting | Observe deliveries from the scenarios above | State badge reflects the outcome: COMPLETED, FAILED, or CANCELLED |
| 8 | Cancel in flight | While a failing delivery waits between attempts, click Cancel | The delivery settles CANCELLED and no further attempts are made |
| 9 | Consistent in-progress state | Watch a failing delivery across its retry window | State stays in progress (scheduled / awaiting retry) throughout, never flips to crashed |
| 10 | Request, response and error detail | Open a delivery's detail page | Request (URL, headers with secrets masked) and Response (status, body, latency) are shown. On a failed delivery an Error block shows the class, message, and remediation |

## UI walkthrough

Annotated screenshots of each step are in the [UI Walkthrough section of PR #9754](https://github.com/opsmill/infrahub/pull/9754#ui-walkthrough).

| Control | Steps shown |
|---------|-------------|
| Retry | Button on the task detail page, confirmation pop-up, notification once done |
| Cancel | Button on the task detail page, confirmation pop-up, notification once done |
| Task tab | The same controls when a delivery is opened from the webhook's Tasks tab |

## Documentation review

Check the user-facing webhook documentation against the observed behaviour.

| Doc | Verify |
|-----|--------|
| `docs/docs/webhooks/overview.mdx`, "Retrying and cancelling deliveries" | The action table matches the UI: Retry is offered when a delivery has finished or is being cancelled; Cancel while it is still running or waiting to retry. |
| `docs/docs/webhooks/overview.mdx`, delivery logging and "When a delivery fails" | The described log contents (target URL, masked headers, truncated payload) and the classified failure reason with its remediation match what the delivery logs show. |

The structured request, response, and error capture is not rendered in the UI yet, so the user docs
deliberately do not describe a request/response panel. Confirm the docs do not claim a UI surface
that is not there.

## Notes

- Secret masking applies to the request signature, environment-sourced header values, and well-known
  credential header names. Standard headers and static header values are shown verbatim.
- Retry produces an independent delivery replaying the frozen payload; the original delivery is kept
  as a record.
- Cancel does not recall an in-flight request; it stops the remaining retries.

See `quickstart.md` for the per-user-story walkthrough and the backend and GraphQL checks.
