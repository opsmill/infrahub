# Simplification tasks

## Implementation

- [X] T033 Replace the custom engine with a compact .github/scripts helper and behavioral tests; collect complete reads, preserve review exemptions, render plain names, and synchronize only configured dashboard/owned labels.
- [X] T034 Replace four-pass workflow with read-only preview and disabled publishing/native-stale jobs; use stock 60/14 timing and add local helper tests to PR CI.
- [X] T035 Remove obsolete custom engine/tests and stale specification artifacts; rewrite developer/operator docs and native Slack reminder setup.
- [X] T036 Validate tests, historical read-only replay, workflow linters and applicable pre-CI; review the simplified design, update PR description and push without activating anything.

## Deployment prerequisites

These are intentionally outside the implementation: select a dedicated dashboard issue and Slack
channel/team/cadence; authorize native Slack settings; run isolated hosted validation; inspect legacy
labels/cache and then review activation separately. No production writes are authorized in this task.
