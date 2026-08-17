# 8. Client-declared request priority, cooperatively trusted

**Status:** Accepted
**Date:** 2026-07-26
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2886-priority-api-backpressure/spec.md` (Assumptions, Governance
Gates), `specs/archive/ifc-2890-frontend-request-priority/research.md` (Open question 1)

## Context

Background work (generators, artifacts, diffs, repository syncs, computed attributes) and
interactive frontend traffic share one finite worker pool and one Neo4j connection pool. Under
background overload the API cannot serve the frontend and the app appears to hang. Shedding the
right traffic first requires knowing which requests a user is waiting on.

The server cannot infer that. A watched live-status poll and a background preload are both
`fetch`/XHR from the same browser origin, with the same auth, hitting the same endpoints. Only the
caller knows the *intent* of a request. Neither the URL, the auth token, nor the origin separates
"a user is watching this" from "this is speculative work".

Accepting an intent declaration from the caller means accepting client-controlled input in the
admission path: any caller can claim `high`. That is a security-adjacent posture decision, not
just a transport detail, and it binds both sides of the wire — so it is recorded once here rather
than per side.

## Decision

**Priority is declared by the caller in an `X-Priority` request header, and the server classifies
solely on that header.** Values are `high` / `medium` / `low`, case-insensitive; a missing, empty,
or unrecognized value resolves to `medium`. No other request property influences the class.

**The claim is trusted.** Under the v1 cooperative first-party trust model — the callers are
Infrahub's own frontend, SDK, and workers — there is no server-side verification that a `high`
claim is legitimate. Enforcement (e.g. token-type classification) is a deliberate deferral, not an
oversight. Adoption is observable through `infrahub_admission_missing_priority_total`.

**The frontend emits the header at the transport boundary, never at call sites.** Each of the four
transports (Apollo GraphQL, the `openapi-fetch` REST client, raw `fetchUrl`, the GraphiQL fetcher)
stamps the header on the way out, defaulting to `high`. The frontend's own type is narrowed to
`'high' | 'low'`: `medium` is the server's fallback for callers that say nothing, so it is
deliberately unrepresentable in frontend code — no frontend-origin request is ever emitted
unheadered or `medium`. Demoting a request to `low` is a single declaration at the query
definition, expressed in each transport's own idiom.

Because the header is client-controlled and the admission gate runs outermost, `x-priority` is
allow-listed in the CORS defaults and CORS preflights bypass admission entirely.

## Consequences

### Positive

- The signal is truthful: it carries intent, which is the only thing that separates interactive
  from background traffic, and it is available at the outermost gate with no auth, routing, or DB
  work.
- Backward compatible and inert on arrival: an un-updated caller is `medium` and sees no change
  until load actually exceeds the derived cap.
- Adding a caller costs one header. No server-side inference table to maintain as endpoints and
  usage patterns change.
- The frontend's narrowed type makes the wrong value a compile error rather than a runtime
  misclassification.

### Negative

- **Any caller can claim `high`.** A misbehaving or hostile client can exempt itself from
  shedding, and a third party who reaches the API can do the same. This is acceptable only while
  the caller set is first-party; exposing the API more broadly requires enforcement first.
- Later enforcement is a breaking change for callers that have grown to rely on an unverified
  `high`.
- Priority correctness is distributed across every caller. A caller that declares badly (a
  background sweep tagged `high`) degrades the protection for everyone, and the server cannot
  detect it.

### Neutral

- The adoption counter is global and unlabeled, so per-origin adoption cannot be sliced out
  directly; it is read as a trend toward the non-frontend floor.
- Origin tagging, if it arrives, is complementary — it answers "who sent this", not "how much does
  the sender care".

## Alternatives Considered

### Server-side origin inference instead of a client-declared header

Rejected as insufficient, not merely inconvenient. The server sees identical requests for watched
polls and background preloads. Inference would have to guess from endpoint and cadence, would be
wrong on exactly the cases the feature exists for, and would need re-tuning whenever the frontend
changes how it fetches.

### Classifying on the auth token or account type

Rejected: it distinguishes *who* is calling, not *what the call is for*. The frontend makes both
interactive and background-shaped requests with the same token, and workers occasionally make
requests a user is waiting on.

### A global registry mapping operation names to priority (frontend)

Rejected: indirection that must be kept in sync with query definitions and drifts silently. The
declaration belongs next to the query it describes.

### Setting the header at each call site (frontend)

Rejected: ~89 interactive call sites would each need a change, and any new call site would default
to wrong. Stamping at the transport boundary makes the safe value automatic and the unsafe value
explicit.

### A React context / provider for priority (frontend)

Rejected: priority is a property of a request, not of the component tree. Polls and background
loads originate outside render.

### Enforcing the `high` claim in v1

Rejected as scope, not as principle. It requires a token-type taxonomy that does not exist yet,
and it is orthogonal to whether the mechanism works. Deferred as a fast-follow, with the exposure
recorded above.
