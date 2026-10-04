# Release Gate Checklist: Enterprise Licensing, Community Contract

**Purpose**: Confirm the answers only people outside this repository can give, before the release that contains this feature is cut
**Created**: 2026-10-04
**Feature**: [spec.md](../spec.md)

Each item needs a named person's answer and the date it was given. Record them under the item when it is checked.

## Telemetry

- [ ] The owner of the cloud telemetry processor confirms it accepts snapshots with `payload_format` `20261004`, the new `TELEMETRY_VERSION`, which carry the `license` field ([telemetry contract](../contracts/telemetry-license-block.md)).
  - Answered by:
  - Date:

## Public documentation

- [ ] Before the first licensing release, the public telemetry pages say that licensed Enterprise deployments send the license ID, type, tiers, issuer and dates, never the customer name: the FAQ (`docs/docs/faq/faq.mdx`) and the telemetry page (`docs/docs/deploy-manage/run-observe/telemetry.mdx`). See [Public documentation](../contracts/telemetry-license-block.md#public-documentation).
  - Answered by:
  - Date:

## Product copy

- [ ] Product signs off the reason explanations for `invalid` and the quiet-mode notes in the banner ([banner contract](../contracts/frontend-banner.md)) and in the upgrade output ([upgrade output contract](../contracts/upgrade-output.md)).
  - Answered by:
  - Date:
