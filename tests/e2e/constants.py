"""Constants shared across the pytest-playwright e2e suite.

Ported from frontend/app/tests/constants.ts so the Python suite uses the exact
same credentials, tokens and dataset definition as the legacy TypeScript suite.
"""

from __future__ import annotations

# Seeded accounts (admin is the bootstrap admin; the others are created by
# models/infrastructure_edge.py and therefore require the `infrastructure_data`
# fixture before they can be used to authenticate).
ADMIN_CREDENTIALS = {"username": "admin", "password": "infrahub"}
READ_WRITE_CREDENTIALS = {"username": "cobrian", "password": "Password123"}
READ_ONLY_CREDENTIALS = {"username": "jbauer", "password": "Password123"}
ENG_TEAM_ONLY_CREDENTIALS = {"username": "shernandez", "password": "Password123"}

# The initial admin API token seeded by infrahub-testcontainers via the
# INFRAHUB_TESTING_INITIAL_ADMIN_TOKEN project variable. This is the same token
# the legacy graphql.ts helper used as the X-INFRAHUB-KEY header.
ADMIN_API_TOKEN = "06438eb2-8019-4776-878c-0941b1f1d1ec"

# The selector that proves a UI session is authenticated (the user menu).
AUTHENTICATED_MENU_TRIGGER = "authenticated-menu-trigger"

# The base schema files loaded as one set. Cross-domain references (e.g. dcim
# references LocationSite / IpamIPAddress) mean the whole directory must be
# applied together, exactly like `infrahubctl schema load models/base`.
BASE_SCHEMA_FILES = (
    "organization.yml",
    "location.yml",
    "dcim.yml",
    "ipam.yml",
    "routing.yml",
    "service.yml",
)
