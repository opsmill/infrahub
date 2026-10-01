# 20. A pre-release UI feature is gated by an experimental settings flag, not by the running version

**Status:** Accepted
**Date:** 2026-08-24
**Author:** @opsmill-team

**Source:** `dev/specs/archive/infp-46-dark-theme-completion/research.md` (R1)

## Context

The dark theme needed to ship before it was finished: complete enough for the team to use daily,
not complete enough to offer every user. Something had to decide which deployments see it.

The original framing called this "enabled on canary deployments". No `canary` concept exists in the
repository, so the mechanism had to be chosen rather than found. The requirement underneath it was
"the deployments we run" — our own stacks, not a customer's.

That requirement is harder to satisfy than it looks, because **nothing in the configuration
identifies a deployment as ours.** Two candidates look like they do and do not:

- `installation_type` is already on the `/api/config` payload, which makes it a tempting lead. It
  distinguishes community from enterprise — a licensing axis, not a production one.
- `INFRAHUB_PRODUCTION` reads like the answer and is set to `false` on every internal stack. But it
  controls the logging output format, and the *shipped* root compose file defaults it to `false` on
  both services, so most customer deployments match it too.

Telemetry cannot answer it either: its endpoint points at OpsMill for every install that has not
opted out, and the only identity in the payload is a per-install UUID minted at database
initialisation. The system is anonymous by construction, so the bit was deliberately never
collected.

## Decision

Gate the feature on an `ExperimentalFeaturesSettings` flag — `dark_theme: bool = False` — and enable
it in the development stack's compose configuration.

The repository already had this convention twice (`graphql_enums`, `value_db_index`), both defaulting
to off with a per-deployment environment override. `experimental_features` is already on the
unauthenticated `/api/config` payload, so the flag is readable before sign-in with no new field and
no new endpoint.

The flag governs **whether the feature exists**, and nothing else. What a user who has not chosen
sees is a separate decision, taken separately (see ADR 0021 and
`dev/knowledge/frontend/theming.md`).

## Consequences

### Positive

- The gate targets deployments directly, which is what was meant, rather than a proxy for them.
- No new dependency and no new endpoint — one fewer governance gate crossed.
- Removing the gate later is a flag deletion, not an unpicking of derived behaviour.

### Negative

- The flag only reaches deployments whose configuration this repository controls. A shared staging
  box or a cloud instance started some other way stays without the feature until someone sets the
  environment variable there. This was raised explicitly and accepted: the deployments the team
  actually runs come from these compose files.

### Neutral

- A customer can opt into an alpha feature by setting the same variable. That is intended — the flag
  expresses "this deployment wants the unfinished thing", not "this deployment belongs to us".

## Alternatives Considered

### Derive the default from the running version (PEP 440 pre-release detection)

Specified first, in detail, and verified against real builds — `1.11.0b2.dev134+geb5acb009` and
`1.11.1rc1` resolve pre-release, `1.11.0` does not. It needed no configuration at all.

Rejected because it gates on the wrong thing. "Pre-release" is a property of a *version*, not of a
deployment: a customer running `1.11.0rc1` in their own staging environment matches it exactly, and
they are not us. It also invented a mechanism where the repository already had one, and it required
parsing PEP 440 versions in the backend — a new dependency for a job an existing convention already
does more precisely.

### `installation_type`

Wrong axis, as above: community versus enterprise, not production versus non-production. Worth
recording explicitly because it is already on the config payload and reads like the answer.

### A frontend build-time environment variable

Baked at asset-build time. The same published assets are served by every deployment, so a locally
built image deployed into a production-like environment would still claim non-production.
