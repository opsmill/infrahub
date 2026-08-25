"""Throwaway prototype gate for webhook payload enrichment.

Read from a raw environment variable rather than an INFRAHUB_ config setting: a real
setting would drag in docker-compose / configuration.mdx regeneration and their CI gates,
which a measurement prototype does not need. The value is re-read per mutation on purpose so
the level can be switched between perf runs without rebuilding the image.
"""

from __future__ import annotations

import os
from enum import StrEnum

_ENV_VAR = "INFRAHUB_EXPERIMENTAL_WEBHOOK_ENRICHMENT"


class WebhookEnrichmentLevel(StrEnum):
    OFF = "off"
    PRIMARY = "primary"
    FULL = "full"


def get_webhook_enrichment_level() -> WebhookEnrichmentLevel:
    """Resolve the active level. An unknown value falls back to OFF (current behaviour)."""
    raw = os.environ.get(_ENV_VAR, "off").strip().lower()
    try:
        return WebhookEnrichmentLevel(raw)
    except ValueError:
        return WebhookEnrichmentLevel.OFF


def enrichment_primary_enabled() -> bool:
    return get_webhook_enrichment_level() in (WebhookEnrichmentLevel.PRIMARY, WebhookEnrichmentLevel.FULL)


def enrichment_full_enabled() -> bool:
    return get_webhook_enrichment_level() == WebhookEnrichmentLevel.FULL
