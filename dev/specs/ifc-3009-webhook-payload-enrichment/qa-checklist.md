# QA Checklist — Labels and HFIDs in webhook node event payloads

**Generated**: 2026-10-01 10:30 local
**Feature**: dev/specs/ifc-3009-webhook-payload-enrichment
**Source**: speckit.opsmill.qa

## Scope

Verify that the node events a webhook delivers identify every object they mention: the changelog carries the node's `display_label` and `hfid`, and each relationship peer carries `peer_display_label` and `peer_hfid`, for GraphQL mutations and for the node events of a branch merge or rebase. Also verify that a peer whose schema lists the node back receives an event naming it. Out of scope: branch lifecycle event payloads, custom webhook transforms, performance, and the secondary-event fixes, which are bug fixes covered by automated tests.

## Prerequisites

- [ ] Working copy is on branch `pmi-webhook-payload-enrichment` with the whole stack merged into it.
- [ ] `uv sync --all-groups` has completed cleanly.
- [ ] Docker is running and port 8200 is free on the host.
- [ ] `jq` is installed.

## Setup

1. Build and start Infrahub from the branch, then load the demo schema and data:

```bash
export INFRAHUB_IMAGE_VER=local
uv run invoke dev.build
uv run invoke dev.start --wait
uv run invoke dev.load-infra-schema
uv run invoke dev.load-infra-data
```

2. In a second terminal, start a receiver that prints every payload it gets:

```bash
cat > /tmp/qa_receiver.py <<'EOF'
from fastapi import FastAPI, Request
import uvicorn
app = FastAPI()
@app.post("/")
async def receive(request: Request):
    print((await request.body()).decode(), flush=True)
    return {"status": "ok"}
uvicorn.run(app, host="0.0.0.0", port=8200, log_level="warning")
EOF
uv run --with fastapi --with uvicorn python /tmp/qa_receiver.py | tee /tmp/qa-webhooks.jsonl
```

3. Log in at `http://localhost:8000` with the administrator account listed in `docs/docs/tutorials/getting-started/readme.mdx`, open the GraphQL sandbox and create a webhook for every event on every branch (on Linux, use the host IP instead of `host.docker.internal`):

```graphql
mutation {
  CoreStandardWebhookCreate(data: {
    name: {value: "qa-enrichment"}, branch_scope: {value: "all_branches"},
    url: {value: "http://host.docker.internal:8200/"}
  }) { ok }
}
```

4. Wait 30 seconds before the first scenario; the first event after creating a webhook can be missed.

## Test Scenarios

### 1. A node update names the node and its new peer

**What this verifies**: an updated node's event carries its own labels, and a changed one-cardinality peer carries its labels.

**Steps**:

- [ ] Run in the sandbox: `mutation { InfraDeviceUpdate(data: {hfid: ["atl1-edge1"], description: {value: "qa"}, platform: {hfid: ["Cisco NXOS SSH"]}}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraDevice") | .data.changelog | {display_label, hfid, platform: .relationships.platform}' /tmp/qa-webhooks.jsonl`
- [ ] Confirm: `hfid` is `["atl1-edge1"]` and `display_label` is `atl1-edge1`.
- [ ] Confirm: `platform.peer_display_label` is `Cisco NXOS SSH`, `platform.peer_hfid` is `["Cisco NXOS SSH"]`, and the previous platform appears only as `peer_id_previous` / `peer_kind_previous`.

**Expected result**: the device event names the device and its new platform without any ID lookup.

### 2. The peers on the other side of the change name the node

**What this verifies**: a peer whose schema lists the node back receives one event naming the node by its labels.

**Steps**:

- [ ] After scenario 1, run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraPlatform") | .data.changelog | {display_label, devices: [.relationships.devices.peers[] | {peer_display_label, peer_hfid, peer_status}]}' /tmp/qa-webhooks.jsonl | tail -2`
- [ ] Confirm: `Cisco NXOS SSH` has one event with the device as peer: `peer_display_label` `atl1-edge1`, `peer_hfid` `["atl1-edge1"]`, `peer_status` `added`.
- [ ] Confirm: the previous platform has one event with the same device and `peer_status` `removed`.

**Expected result**: both platforms are told which device joined or left them, by name.

### 3. A branch merge delivers enriched node events

**What this verifies**: node events emitted by a merge carry the same fields as those of a mutation.

**Steps**:

- [ ] Run: `mutation { BranchCreate(data: {name: "qa-merge"}) { ok } }`
- [ ] Open the sandbox on branch `qa-merge` and run the scenario 1 mutation with `description: {value: "qa-merge"}`.
- [ ] Run on `main`: `mutation { BranchMerge(data: {name: "qa-merge"}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .branch=="main") | .data.changelog | {hfid, display_label}' /tmp/qa-webhooks.jsonl | tail -1`

**Expected result**: the event emitted on `main` for the device carries `hfid` `["atl1-edge1"]` and its display label.

### 4. A rebase delivers enriched node events

**What this verifies**: node events emitted by a rebase on the rebased branch carry the labels.

**Steps**:

- [ ] Run: `mutation { BranchCreate(data: {name: "qa-rebase"}) { ok } }`, then on `main` update another device's description.
- [ ] Run: `mutation { BranchRebase(data: {name: "qa-rebase"}) { ok } }`
- [ ] Run: `jq -c 'select(.branch=="qa-rebase" and .event=="infrahub.node.updated") | .data.changelog | {node_kind, hfid, display_label}' /tmp/qa-webhooks.jsonl`

**Expected result**: the rebase emits an event for that device on `qa-rebase`, with its `hfid` and display label.

## Edge Cases

- [ ] Kind without an HFID: create an `IpamIPAddress` → its `infrahub.node.created` changelog has `hfid` `null` and a `display_label`.
- [ ] HFID change: rename a device → the event carries the new name in `hfid`.
- [ ] Peer without an HFID, one-way relationship: `RelationshipAdd` two tags to the device (`nodes: [{id: "<tag-id>"}]`) → the device event lists both under `relationships.tags.peers` with `peer_display_label` set and `peer_hfid` `null`; the tags receive no event, since a tag does not list what points at it.
- [ ] Cascade delete: delete a device → every event is delivered; no delivery fails in the webhook's task list.

## Teardown

```bash
uv run invoke dev.destroy
rm -f /tmp/qa_receiver.py /tmp/qa-webhooks.jsonl
```

Stop the receiver with Ctrl+C.

## Sign-off

- [ ] All scenarios above pass.
- [ ] No unexpected output, warnings, or errors observed.
- [ ] Tester: ______________________  Date: __________
