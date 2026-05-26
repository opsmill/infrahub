# Manual Test Plan — Auto-create Account Groups ([IFC-2521](https://opsmill.atlassian.net/browse/IFC-2521) — [INFP-556](https://opsmill.atlassian.net/browse/INFP-556))

Manual / live-instance walkthrough for the full feature as merged into `develop`:

- Core MVP (filter, name capture, idempotency, default-group fallback, per-login cap, `origin` attribute) — squashed under [PR #9302](https://github.com/opsmill/infrahub/pull/9302) → develop
- Audit events layer (`GroupAutoCreatedEvent`, `GroupAutoCreateRejectedEvent`, `GroupAutoCreateCappedEvent` + typed GraphQL `Events` query + `group_auto_create` filter) — squashed under [PR #9325](https://github.com/opsmill/infrahub/pull/9325) → develop
- User-facing docs polish — squashed under [PR #9340](https://github.com/opsmill/infrahub/pull/9340) → develop

Scenarios A–D restate the [PR #9302](https://github.com/opsmill/infrahub/pull/9302) walkthrough; new event/origin/docs verifications are appended to each scenario and as scenarios E–H.

---

## Prerequisites

- Any OIDC IdP that emits a `groups` claim — Keycloak in Docker is used below.
- Local Infrahub built from origin/develop.
- A second browser (or incognito session) for the local `admin` to query the API/UI while the test user is signed in via SSO.

## 0 — Bring up Keycloak and configure the backend

The deps, task-manager, and Keycloak run in Docker via `dev.deps`; the API server, task worker, and frontend run natively.

### 0a — Write the dev-override (Keycloak + dep ports for native reach)

```sh
cat > development/docker-compose.dev-override.yml <<'YAML'
---
services:
  database:
    ports: ["7687:7687", "7474:7474"]
  message-queue:
    ports: ["5672:5672", "15672:15672"]
  cache:
    ports: ["6379:6379"]
  task-manager:
    ports: ["4200:4200"]

  keycloak:
    image: quay.io/keycloak/keycloak:25.0.6
    command: ["start-dev", "--import-realm"]
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin
      KC_HOSTNAME: localhost
      KC_HOSTNAME_PORT: 8180
      KC_HOSTNAME_STRICT: "false"
      KC_HTTP_ENABLED: "true"
    ports: ["127.0.0.1:8180:8080"]
    volumes:
      - "keycloak_data:/opt/keycloak/data"
      - "./keycloak/import:/opt/keycloak/data/import:ro"

volumes:
  keycloak_data:
YAML
```

### 0b — Drop the realm import

Write `development/keycloak/import/realm.json`. The realm needs:

- Groups: `ops-admins`, `ops-readers`, `data-engineers`, `noise-group`
- User `alice` (firstName=Alice, lastName=Admin) in `ops-admins`, `data-engineers`, `noise-group`
- Client `my-oauth2` with a `groups` mapper (`oidc-group-membership-mapper`, `full.path=false`) and `redirectUris` containing both `http://localhost:8000/*` and `http://localhost:8080/*`

```sh
mkdir -p development/keycloak/import
cat > development/keycloak/import/realm.json <<'JSON'
{
  "realm": "infrahub-test",
  "enabled": true,
  "sslRequired": "none",
  "groups": [
    {"name": "ops-admins", "path": "/ops-admins"},
    {"name": "ops-readers", "path": "/ops-readers"},
    {"name": "data-engineers", "path": "/data-engineers"},
    {"name": "noise-group", "path": "/noise-group"}
  ],
  "users": [{
    "username": "alice",
    "enabled": true,
    "emailVerified": true,
    "firstName": "Alice",
    "lastName": "Admin",
    "email": "alice@example.com",
    "credentials": [{"type": "password", "value": "alice", "temporary": false}],
    "groups": ["/ops-admins", "/data-engineers", "/noise-group"]
  }],
  "clients": [{
    "clientId": "my-oauth2",
    "enabled": true,
    "protocol": "openid-connect",
    "publicClient": false,
    "secret": "infrahub-dev-secret-not-for-prod",
    "standardFlowEnabled": true,
    "redirectUris": ["http://localhost:8000/*", "http://localhost:8080/*"],
    "webOrigins": ["+"],
    "protocolMappers": [{
      "name": "groups",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-group-membership-mapper",
      "config": {
        "full.path": "false",
        "id.token.claim": "true",
        "access.token.claim": "true",
        "userinfo.token.claim": "true",
        "claim.name": "groups"
      }
    }]
  }]
}
JSON
```

### 0c — Export the full backend config in the shell

```sh
# Addresses (deps reachable from host because 0a exposes their ports)
export INFRAHUB_DB_ADDRESS=localhost
export INFRAHUB_BROKER_ADDRESS=localhost
export INFRAHUB_CACHE_ADDRESS=localhost
export INFRAHUB_WORKFLOW_ADDRESS=localhost
export INFRAHUB_PUBLIC_URL=http://localhost:8080
export INFRAHUB_API_CORS_ALLOW_ORIGINS='["http://localhost:8080"]'

# Native-run paths (defaults point at /opt/infrahub which needs root on macOS)
mkdir -p /tmp/infrahub-test/storage /tmp/infrahub-test/git
export INFRAHUB_STORAGE_LOCAL_PATH=/tmp/infrahub-test/storage
export INFRAHUB_INTERNAL_ADDRESS=http://localhost:8000
export INFRAHUB_METRICS_PORT=8001
export PREFECT_API_URL=http://localhost:4200/api
export GIT_CONFIG_GLOBAL=/tmp/infrahub-test/.gitconfig

# OIDC provider config
export INFRAHUB_SECURITY_OIDC_PROVIDERS='["provider1"]'
export INFRAHUB_OIDC_PROVIDER1_CLIENT_ID=my-oauth2
export INFRAHUB_OIDC_PROVIDER1_CLIENT_SECRET=infrahub-dev-secret-not-for-prod
export INFRAHUB_OIDC_PROVIDER1_DISCOVERY_URL=http://localhost:8180/realms/infrahub-test/.well-known/openid-configuration
export INFRAHUB_OIDC_PROVIDER1_DISPLAY_LABEL=Keycloak
export INFRAHUB_OIDC_PROVIDER1_USERINFO_METHOD=post

# Per-scenario auto-create config
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='^(?P<name>(ops|data)-.*)$'
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_MAX_PER_LOGIN=5
```

### 0d — Bring the deps up

```sh
uv run invoke dev.deps        # Neo4j + message bus + cache + task-manager + Keycloak
```

### 0e — Start the API server, task worker, and frontend

Run each in its own shell so logs stay separate. Shells 1 and 2 must inherit the exports from 0c.

```sh
# Shell 1: API server (auto-reloads on code change)
uv run infrahub server start --listen 0.0.0.0 --port 8000

# Shell 2: task worker
uv run prefect worker start --type infrahubasync --pool infrahub-worker --with-healthcheck

# Shell 3: frontend (Vite dev server on :8080 — the URL you use in the browser)
cd frontend/app && pnpm setup        # first time only — initializes submodules + installs deps
cd frontend/app && pnpm start
```

### 0f — Sanity-check the stack

```sh
docker ps --format '{{.Names}} {{.Status}}'                                                # every container Up / healthy
curl -sf http://localhost:8180/realms/infrahub-test/.well-known/openid-configuration >/dev/null && echo "keycloak OK"
curl -sf http://localhost:8000/api/config -o /tmp/cfg.json && \
  python3 -c 'import json;c=json.load(open("/tmp/cfg.json",encoding="utf-8",errors="replace"));assert c["sso"]["enabled"],"sso DISABLED";print("infrahub sso OK, providers=",[p["name"] for p in c["sso"]["providers"]])'
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:8080/ | grep -q 200 && echo "frontend OK"
```

Open <http://localhost:8080> in a browser — the login page must show a "Continue with Keycloak" button.

To re-apply env changes mid-test, edit the export(s) and Ctrl-C → restart Shell 1 (and Shell 2 if you changed worker-side envs). Shell 3 doesn't need restarts.

### Reusable GraphQL probes

Open the GraphQL sandbox as `admin` at <http://localhost:8000/graphql> and keep these queries handy.

**Probe 1 — list every auto-create event in chronological order**

```graphql
query AutoCreateEvents {
  InfrahubEvent(
    event_type: [
      "infrahub.group.auto_created"
      "infrahub.group.auto_create_rejected"
      "infrahub.group.auto_create_capped"
    ]
    order: ASC
  ) {
    count
    edges {
      node {
        id
        event
        occurred_at
        ... on GroupAutoCreatedEventType {
          idp
          protocol
          triggering_user_name
          group_id
          group_name
          source_pattern
          origin_value
        }
        ... on GroupAutoCreateRejectedEventType {
          idp
          protocol
          triggering_user_name
          rejected_claim_value
        }
        ... on GroupAutoCreateCappedEventType {
          idp
          protocol
          triggering_user_name
          cap_value
          dropped_count
          dropped_claims
        }
      }
    }
  }
}
```

**Probe 2 — `group_auto_create` filter (idp + protocol)**

```graphql
query AutoCreateEventsByIdp {
  InfrahubEvent(
    event_type_filter: {
      group_auto_create: { idp: ["provider1"], protocol: ["oidc"] }
    }
    order: ASC
  ) {
    count
    edges { node { id event } }
  }
}
```

The `group_auto_create` sub-filter is silently ignored on non-auto-create events, so you don't strictly need to combine it with `event_type:` — but adding the explicit list keeps results unambiguous.

**Probe 3 — inspect `origin` on every account group**

```graphql
query AccountGroupsOrigin {
  CoreAccountGroup {
    edges {
      node {
        id
        name { value }
        origin { value }
      }
    }
  }
}
```

---

## Scenario A — Happy path, filter exclusion, `origin`, and the created-event

1. Sign in as `alice` / `alice` via the Keycloak button.
2. As `admin`, open `/role-management/groups`.
3. **Expect** two new rows: `ops-admins` and `data-engineers`, with `alice` as a member of each.
4. On each row, open the detail page → toggle **Extra** (eye icon) → `origin` is `provider1`. The field is rendered read-only (no edit affordance).
5. `noise-group` is **not** present — it matched neither the captured name nor the filter.
6. Run **Probe 1**: exactly **two** `GroupAutoCreatedEventType` events. For each one:
   - `idp = "provider1"`, `protocol = "oidc"`
   - `triggering_user_name = "Alice Admin"`
   - `source_pattern = "^(?P<name>(ops|data)-.*)$"`
   - `origin_value = "provider1"` (matches the `origin` attribute on the group)
   - `group_id` matches the group's UUID from the UI
   - `group_name` is `ops-admins` or `data-engineers`
7. Run **Probe 3**: `origin.value` is `"provider1"` on the two new rows and is `null` on every pre-existing group (`Infrahub Users`, admin-seeded rows, etc.).

## Scenario B — Filter excludes unrelated claims (no event emitted)

Continuing from Scenario A:

1. Run **Probe 1** again.
2. **Expect** no event whose `group_name` is `noise-group` and no rejected event for it — filter exclusion is silent.
3. **Expect** no group named `noise-group` in the UI.

## Scenario C — Idempotency on the second login (no duplicate event)

1. Sign `alice` out and back in.
2. Re-run **Probe 1**.
3. **Expect** the event count is **unchanged** (still 2). Reusing existing groups does not emit `GroupAutoCreatedEvent`.
4. **Expect** the group list is unchanged (same two rows, same UUIDs, same `origin`).

## Scenario D — Per-login cap and `GroupAutoCreateCappedEvent`

1. Edit the Keycloak realm to give a fresh user `carol` membership in ~12 new `ops-*` groups (any names that match the filter and don't yet exist locally).
2. Recreate Keycloak's data so the new realm import lands:

   ```sh
   docker rm -fv keycloak && docker volume rm <stack>_keycloak_data
   uv run invoke dev.deps
   ```

3. Keep `INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_MAX_PER_LOGIN=5` exported — no restart needed unless you changed the value.
4. Sign in as `carol`. Login **must succeed**.
5. Server logs show `auth_groups.skip_claim_over_per_login_cap` lines, one per dropped claim, each carrying `effective_name=...` and `max_per_login=5`.
6. UI: exactly **5** new `ops-*` groups exist, each with `origin=provider1`.
7. Run **Probe 1**:
   - 5 new `GroupAutoCreatedEventType` events (one per created group).
   - Exactly **one** `GroupAutoCreateCappedEventType` event with:
     - `cap_value = 5`
     - `dropped_count` equals the number of matching claims beyond 5 (7 if you added 12)
     - `dropped_claims` is the verbatim list of those claim values (each entry length-truncated)
     - `idp = "provider1"`, `protocol = "oidc"`, `triggering_user_name` equals carol's display name (the OIDC `name` claim — `firstName + lastName` as set in the realm)
8. Sign `carol` in a second time. Re-run **Probe 1** — neither the created nor the capped event count changes (existing-group reuse is uncapped and not audited as creation).

## Scenario E — Rejected claim emits `GroupAutoCreateRejectedEvent`

The rejection path fires when a claim matches the filter but the captured name is not a usable Infrahub group identifier (empty, whitespace-only, etc.).

1. Add a new Keycloak group whose path triggers an empty named capture under a permissive filter — easiest setup:
   - Add group `pad-` (or any name that the filter captures into an empty/whitespace string) and put a user `bob` in it.
   - Switch the backend's filter so the capture group can produce an empty string:

     ```sh
     export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='^pad-(?P<name>.*)$'
     ```

   - In Shell 1, Ctrl-C and re-run the API-server command from 0e (`uv run infrahub server start --listen 0.0.0.0 --port 8000`) so the new `INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER` is picked up.
2. Sign in as `bob`. Login **must succeed**.
3. **Expect** no new `CoreAccountGroup` named `""` or whitespace; the offending claim is dropped silently from the user's perspective.
4. Run **Probe 1**:
   - One new `GroupAutoCreateRejectedEventType` event.
   - `rejected_claim_value` holds the original verbatim claim (`pad-`), length-truncated.
   - `idp = "provider1"`, `protocol = "oidc"`, `triggering_user_name` equals bob's display name (the OIDC `name` claim — `firstName + lastName` as set in the realm).
5. Run **Probe 3** — no new row with a null/whitespace `name.value` exists.

Restore the original filter (`'^(?P<name>(ops|data)-.*)$'`) and Ctrl-C → re-run the API-server command from 0e in Shell 1 before moving on.

## Scenario F — `origin` is read-only and unset on non-auto-created groups

`origin` is omitted from `CoreAccountGroupUpdateInput` and `CoreAccountGroupCreateInput`, so every external write attempt fails at **GraphQL parse time**.

For an auto-created group from Scenario A (e.g. `ops-admins`):

1. **UI**: detail page → click the **Extra** button (eye icon) in the Details card header → `origin` row appears as read-only with the eye indicator and no edit affordance.
2. **GraphQL update attempt** as `admin` (replace `<id>` with the group's UUID):

   ```graphql
   mutation { CoreAccountGroupUpdate(data: { id: "<id>", origin: { value: "tampered" } }) { ok } }
   ```

   **Expect** a parse-time error: `Field 'origin' is not defined by type 'CoreAccountGroupUpdateInput'.` Re-read with **Probe 3** — `origin.value` is still `"provider1"`.

For a manually-created group:

1. **GraphQL create attempt** supplying `origin`:

   ```graphql
   mutation { CoreAccountGroupCreate(data: { name: { value: "manual-test" }, origin: { value: "manual-attempt" } }) { object { id } } }
   ```

   **Expect** a parse-time error: `Field 'origin' is not defined by type 'CoreAccountGroupCreateInput'.`
2. Re-run without the `origin` field — the create succeeds; re-read via **Probe 3** — `origin.value` is `null`.

For a pre-existing group (any row that existed before the upgrade — e.g. `Infrahub Users`, `Super Administrators`):

1. **Probe 3** confirms `origin.value` is `null` — no migration backfill ran.

## Scenario G — Default-group fallback (no auto-create events)

1. Set:

   ```sh
   export INFRAHUB_SECURITY_SSO_USER_DEFAULT_GROUP=<existing-group-with-a-role>   # e.g. "Infrahub Users"
   export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='^(?P<name>nope-.*)$'
   ```

2. Restart the native API server (Ctrl-C in Shell 1, re-run `uv run infrahub server start --listen 0.0.0.0 --port 8000`).
3. Sign in as `alice` (whose claims match nothing under `^nope-.*$`).
4. Server logs show `auth_groups.default_group_fallback_applied`.
5. `alice` is a member of the default group; no new groups are created on this login.
6. Run **Probe 1** — the event counts are unchanged from before this scenario. The fallback path emits **no** auto-create events.

## Scenario H — Docs polish ([PR #9340](https://github.com/opsmill/infrahub/pull/9340))

Build the docs site and confirm the new content renders.

```sh
cd docs
npm install              # first time only
npm run start            # dev server with hot-reload — or `npm run build && npm run serve` for the prod-style static build
```

1. Visit [**`/docs/deploy-manage/user-management/sso/advanced-sso`**](http://localhost:3000/docs/deploy-manage/user-management/sso/advanced-sso) → the **"Auto-create groups from identity provider claims"** section is present and ready for review.
2. Follow the link → [**`/docs/reference/infrahub-events/group`**](http://localhost:3000/docs/reference/infrahub-events/group) → all three auto-create event types are present with full payload tables.

---

## Cleanup

Unset the per-scenario / SSO envs:

```sh
unset INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER \
      INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_MAX_PER_LOGIN \
      INFRAHUB_SECURITY_SSO_USER_DEFAULT_GROUP
```

Ctrl-C the `infrahub server start` and `prefect worker start` shells. The Vite dev server (Shell 3) holds no state and can be left running between sessions — Ctrl-C it only if you want the port back. Then `uv run invoke dev.stop` to take the deps + Keycloak down (or `dev.destroy` to also wipe Neo4j/message-bus volumes).

Existing auto-created groups remain on the next bring-up; lifecycle/cleanup is [INFP-536](https://opsmill.atlassian.net/browse/INFP-536) and out of scope here.
