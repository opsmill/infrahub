# Infrahub threat model

## What Infrahub does

Infrahub is a source of truth for network and infrastructure automation. Teams store their devices, interfaces,
IP addresses and other infrastructure data in it, change that data in branches, review the changes in proposed
changes, and merge them. Automation tools read the data through the API to generate and deploy configuration to
network devices. Someone who can change data in Infrahub without permission can change what gets deployed to
production networks.

Infrahub is a web application: a Python backend (FastAPI, GraphQL, Neo4j, RabbitMQ, Redis, Prefect task workers)
and a React frontend. The documentation for the intended behavior is in `dev/knowledge/backend/`, in particular
`authentication.md`, `permissions.md`, `webhooks.md`, `git-sync.md`, `computed-attributes.md` and `templates.md`.

## Where untrusted input enters

- The GraphQL API (`/graphql` and `/graphql/<branch>`) and the REST API (`/api/...`), from anonymous users and from
  signed-in accounts with any role.
- Sign-in: passwords, JWT access and refresh tokens, API tokens (`X-INFRAHUB-KEY` header), and OAuth2 / OIDC
  single sign-on, including the redirect and callback flow.
- Files that accounts upload (file objects) and artifacts that Infrahub stores and serves back.
- Data that accounts write and that other users later view in the frontend.
- Jinja2 templates in the schema (computed attributes and display labels). Accounts that can change the schema
  write these templates, and Infrahub renders them in a sandboxed Jinja2 environment.
- Webhook definitions, which make Infrahub send HTTP requests to a URL that the account managing the webhook sets.

## Who is trusted

- Anonymous users can read data when anonymous access is turned on (the default). What they can read is set by the
  "Anonymous User" role. Reading what that role allows is expected.
- Signed-in accounts can do only what their roles and permissions allow (global permissions such as
  `EDIT_DEFAULT_BRANCH`, `MERGE_PROPOSED_CHANGE` or `MANAGE_SCHEMA`, and object permissions per kind and branch).
  Any way to go beyond those permissions is in scope.
- Accounts with `SUPER_ADMIN` are fully trusted.
- Git repositories connected to Infrahub are trusted like code. The task workers run the Python transforms, checks
  and generators from these repositories, and render their Jinja2 template files without a sandbox. This is by
  design. Connecting a repository requires permission to do so.

## Components in scope

- `backend/infrahub/`: API, GraphQL, authentication, permissions, branches, merges, proposed changes, schema,
  storage, webhooks, task workers and the Git integration.
- `frontend/app/`: the web interface.

## Out of scope

- `python_sdk/` and `frontend/packages/schema-visualizer/`: separate projects pulled in as Git submodules.
- `docs/`, `models/`, `utilities/`, `tasks/`, `development/`, `tests/`, `backend/tests/`, `frontend/app/tests/`
  and `python_testcontainers/`: documentation, example data, developer tooling and tests.
- The default passwords, tokens and secret key in `docker-compose.yml` and in this image's start script. They are
  development defaults: the documentation describes the Docker Compose deployment as suitable for local development
  and demo environments, not for production.
- Vulnerabilities in third-party dependencies, unless Infrahub uses the dependency in an unsafe way.
- Denial of service that requires `SUPER_ADMIN`.

## How we rate severity

- **Critical:** code execution on the server or task workers without an account or with a low-privilege account,
  signing in as another account without its credentials, or reading or changing any data without an account.
- **High:** a signed-in account going beyond its permissions (for example changing the default branch without
  `EDIT_DEFAULT_BRANCH`, merging without merge permission, or managing accounts or permissions without the matching
  permission), reading data its roles do not allow, reading stored secrets or credentials, escaping the Jinja2
  sandbox for schema templates, and stored XSS that runs in another account's session.
- **Medium:** denial of service that a low-privilege or anonymous user can trigger, leaks of data that is not
  sensitive on its own, reflected XSS or CSRF that needs the victim to take an action, and open redirects in the
  sign-in flow.
- **Low:** missing hardening (security headers, cookie flags) and verbose error messages without sensitive data.

## How to exercise Infrahub

The image has every service installed. They listen on localhost only.

- `.oss-scanner/start-services.sh all` starts Neo4j, RabbitMQ, Redis, the Prefect task manager, the API server on
  `http://localhost:8000` and one task worker. Sign in as `admin` / `infrahub`, or send the header
  `X-INFRAHUB-KEY: 06438eb2-8019-4776-878c-0941b1f1d1ec`. Logs are in `/var/log/infrahub-scanner`.
- To test permissions, create an account with a limited role through the GraphQL API as admin, then send requests
  as that account.
- `.oss-scanner/start-services.sh deps` starts only the services the backend tests need. Run tests with
  `uv run pytest backend/tests/unit/<path>`. The tests reset the database, so stop the API server first
  (`.oss-scanner/start-services.sh stop`).
- Frontend unit tests: `cd frontend/app && pnpm vitest run <path>`. They run in a headless Chromium that the image
  build tries to install; if the build log shows a warning about it, these tests cannot run.

## How we would like reports and patches

- One report per root cause. Group findings that share the same missing check.
- Include a proof of concept that runs against the API server started above (a `curl` command or a short Python
  script), and the role and permissions of the account that sends it.
- Patches should be minimal, follow the existing code style, and add a test under `backend/tests/` or
  `frontend/app/tests/` that fails without the fix.
