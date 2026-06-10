"""Composable demo-dataset fixtures for the pytest-playwright e2e suite.

This package decomposes the monolithic ``infrahubctl run
models/infrastructure_edge.py`` data load into small, standalone,
session-scoped pytest fixtures built directly on the sync Infrahub SDK
(no subprocess, no external script). Each module owns one slice of the
dataset and returns a typed handle describing what it created, so
downstream slices depend on handles instead of hidden in-process state
(the script's ``client.store`` / ``INTERFACE_OBJS`` globals).

Conventions every slice follows:

* **Sync SDK only** (``InfrahubClientSync``), matching the all-sync harness.
* **Session-scoped and idempotent**: saves use ``allow_upsert`` where the
  script did, so a slice can run against a stack that already carries it.
* **External-mode no-op**: when ``INFRAHUB_ADDRESS`` points at an
  already-provisioned Infrahub, fixtures return their handle without
  writing anything (mirroring the script-based fixtures they replace).
* **Dataset-faithful**: the data must stay byte-equivalent to the script's
  medium profile (5 sites x 6 devices, BGP mesh, scenario branches) until
  every consuming test is rewired; parity is checked with
  ``tests/e2e/data/parity.py``.

The modules are registered as pytest plugins from ``tests/e2e/conftest.py``.
"""
