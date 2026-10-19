# QA Checklist — Labels and HFIDs in webhook node event payloads

**Generated**: 2026-10-01 10:30 local
**Feature**: dev/specs/ifc-3009-webhook-payload-enrichment
**Source**: speckit.opsmill.qa

## Scope

Verify that the node events a webhook delivers identify every object they mention: the changelog carries the node's `display_label` and `hfid`, and each relationship peer carries `peer_display_label` and `peer_hfid`, for GraphQL mutations and for the node events of a branch merge or rebase. Also verify that a peer whose schema lists the node back receives an event naming it. Out of scope: branch lifecycle event payloads, custom webhook transforms, performance, and the secondary-event fixes.

## Prerequisites

- [ ] Working copy is on `develop` at a commit that includes [PR #10833](https://github.com/opsmill/infrahub/pull/10833).
- [ ] `uv sync --all-groups` has completed cleanly.
- [ ] Docker is running and port 8200 is free on the host.
- [ ] `jq` is installed.

## Setup

1. Build and start Infrahub from `develop`, then load the demo schema and data:

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
    url: {value: "http://host.docker.internal:8200/"},
    shared_key: {value: "qa-shared-key"}
  }) { ok }
}
```

4. Update the description of any device and wait until its `infrahub.node.updated` event appears in `/tmp/qa-webhooks.jsonl`. Repeat if it does not arrive within a minute: the events sent just after a webhook is created can be missed, for longer while the workers still process the demo data load.

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

**What this verifies**: the node events a rebase emits on the rebased branch, for the changes made on that branch, carry the labels.

**Steps**:

- [ ] Run: `mutation { BranchCreate(data: {name: "qa-rebase"}) { ok } }`
- [ ] Open the sandbox on branch `qa-rebase` and run: `mutation { InfraDeviceUpdate(data: {hfid: ["atl1-edge2"], description: {value: "qa-rebase"}}) { ok } }`
- [ ] On `main`, update the description of `atl1-core1`.
- [ ] Run: `mutation { BranchRebase(data: {name: "qa-rebase"}) { ok } }`
- [ ] Run: `jq -c 'select(.branch=="qa-rebase" and .event=="infrahub.node.updated") | .data.changelog | {node_kind, hfid, display_label}' /tmp/qa-webhooks.jsonl`

**Expected result**: the rebase emits an event on `qa-rebase` for `atl1-edge2`, with `hfid` `["atl1-edge2"]` and its display label. It emits no event on `qa-rebase` for `atl1-core1`, because a rebase replays the changes made on `main` only for the kinds whose schema the branch changed.

### 5. The display label mutation publishes the full HFID

**What this verifies**: `InfrahubUpdateDisplayLabel` loads only the node's display label, and its event still carries the node's full HFID, including the part read through a relationship.

**Steps**:

- [ ] Get an interface of `atl1-edge1`: `query { InfraInterfaceL3(device__name__value: "atl1-edge1", limit: 1) { edges { node { id hfid } } } }`. Its `hfid` has two parts: the device name and the interface name.
- [ ] Run: `mutation { InfrahubUpdateDisplayLabel(data: {id: "<interface-id>", kind: "InfraInterfaceL3", value: "qa-label"}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraInterfaceL3") | .data.changelog | {display_label, hfid}' /tmp/qa-webhooks.jsonl | tail -1`

**Expected result**: `display_label` is `qa-label`, and `hfid` is the two-part HFID the query returned.

### 6. The computed attribute mutation publishes the full HFID

**What this verifies**: `InfrahubUpdateComputedAttribute` loads only the attribute it sets, and its event still carries the node's full HFID.

**Steps**:

- [ ] Run: `mutation { InfrahubUpdateComputedAttribute(data: {id: "<atl1-edge1-id>", kind: "InfraDevice", attribute: "computed_description", value: "qa-computed"}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraDevice") | .data.changelog | {hfid, computed_description: .attributes.computed_description.value}' /tmp/qa-webhooks.jsonl | tail -1`

**Expected result**: `computed_description` is `qa-computed`, and `hfid` is `["atl1-edge1"]`, not an empty list.

### 7. A relationship that feeds the display label

**What this verifies**: after a relationship mutation on a relationship that the display label reads, the event carries the display label computed from the new peer, not the value stored before the mutation.

**Steps**:

- [ ] Load a schema in which the display label of a shirt reads its color:

```bash
cat > /tmp/qa_shirt_schema.yml <<'EOF'
version: "1.0"
nodes:
  - name: Color
    namespace: Testing
    display_label: "{{ name__value }}"
    human_friendly_id: ["name__value"]
    attributes:
      - name: name
        kind: Text
        unique: true
  - name: Shirt
    namespace: Testing
    display_label: "{{ name__value }} {{ color__name__value }}"
    human_friendly_id: ["name__value"]
    attributes:
      - name: name
        kind: Text
        unique: true
    relationships:
      - name: color
        peer: TestingColor
        cardinality: one
        optional: true
EOF
INFRAHUB_ADDRESS=http://localhost:8000 INFRAHUB_API_TOKEN=06438eb2-8019-4776-878c-0941b1f1d1ec uv run infrahubctl schema load /tmp/qa_shirt_schema.yml
```

- [ ] Create a color and a shirt without a color: `mutation { TestingColorCreate(data: {name: {value: "red"}}) { object { id } } TestingShirtCreate(data: {name: {value: "polo"}}) { object { id } } }`
- [ ] Run: `mutation { RelationshipAdd(data: {id: "<shirt-id>", name: "color", nodes: [{id: "<color-id>"}]}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="TestingShirt") | .data.changelog | {display_label, hfid}' /tmp/qa-webhooks.jsonl | tail -1`

**Expected result**: `display_label` is `polo red` and `hfid` is `["polo"]`.

## Edge Cases

- [ ] Kind without an HFID: create an `IpamIPAddress` → its `infrahub.node.created` changelog has `hfid` `null` and a `display_label`.
- [ ] HFID change: rename a device → the event carries the new name in `hfid`.
- [ ] Peer without an HFID, one-way relationship: add two tags to the device with `mutation { RelationshipAdd(data: {id: "<device-id>", name: "tags", nodes: [{id: "<tag1-id>"}, {id: "<tag2-id>"}]}) { ok } }` → the device event lists both under `relationships.tags.peers` with `peer_display_label` set and `peer_hfid` `null`; the tags receive no event, since a tag does not list what points at it.
- [ ] Cascade delete: delete a device → every event is delivered; no delivery fails in the webhook's task list.

## Teardown

```bash
uv run invoke dev.destroy
rm -f /tmp/qa_receiver.py /tmp/qa-webhooks.jsonl /tmp/qa_shirt_schema.yml
```

Stop the receiver with Ctrl+C.

## Sign-off

- [ ] All scenarios above pass.
- [ ] No unexpected output, warnings, or errors observed.
- [ ] Tester: ______________________  Date: __________
