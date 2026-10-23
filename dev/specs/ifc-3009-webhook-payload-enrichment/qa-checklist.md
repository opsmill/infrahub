# QA Checklist — Labels and HFIDs in webhook node event payloads

**Generated**: 2026-10-01 10:30 local
**Feature**: dev/specs/ifc-3009-webhook-payload-enrichment
**Source**: speckit.opsmill.qa

## Scope

Verify that the node events a webhook delivers identify every object they mention: the changelog carries the node's `display_label` and `hfid`, and each relationship peer carries `peer_display_label` and `peer_hfid`, for GraphQL mutations and for the node events of a branch merge or rebase. Also verify that a peer whose schema lists the node back receives an event naming it. Out of scope: branch lifecycle event payloads, custom webhook transforms, performance, and the secondary-event fixes.

Each scenario that the web interface can drive has two paths: one through the GraphQL sandbox and one through the web interface, because the interface sends its own mutations (a form saves through the node update mutation, a relationship tab through `RelationshipAdd` / `RelationshipRemove`, a proposed change merges through its own flow). Run both paths. A scenario with only a GraphQL path uses a mutation that the web interface does not send.

## Areas whose performance the enrichment can affect

This checklist does not measure performance. These actions now look up the names of the objects they change, so they can take longer than before, more so when an object has many related objects:

- Creating, editing, upserting or deleting an object, in the web interface or through GraphQL.
- Deleting an object with many related objects, such as a group with many members.
- Adding or removing related objects in a relationship tab, or with `RelationshipAdd` / `RelationshipRemove`.
- Adding or removing a profile on an object.
- Setting a display label or a computed attribute value with `InfrahubUpdateDisplayLabel` / `InfrahubUpdateComputedAttribute`.
- Allocating an IP prefix or address from an IP pool.
- Merging a branch, directly or through a proposed change, more so with thousands of changed objects.
- Rebasing a branch.
- Receiving webhooks: each payload is larger, by the names of the related objects it lists.

Live measurements: [IFC-3100](https://opsmill.atlassian.net/browse/IFC-3100?focusedCommentId=43928).

## Prerequisites

- [ ] Working copy is on `develop` at a commit that includes [PR #10833](https://github.com/opsmill/infrahub/pull/10833).
- [ ] `uv sync --all-groups` has completed cleanly.
- [ ] Docker is running and port 8200 is free on the host.
- [ ] `jq` is installed.

## Setup

1. Start Infrahub from `develop` and load the demo schema. The `dev.*` tasks mount the working copy into the containers, so the image only needs a rebuild (`uv run invoke dev.build`) when `uv.lock` or the `python_sdk` submodule changed since the image was built.

```bash
export INFRAHUB_IMAGE_VER=local
uv run invoke dev.start --wait
uv run invoke dev.load-infra-schema
```

2. Wait until the `service_identifier` number pool exists, then load the demo data. The schema load creates this pool asynchronously, and the data load fails with "The pool for service_identifier has not been provisioned yet" when it runs first. A failed data load cannot be re-run: it fails on the nodes the first run created, so restart from `uv run invoke dev.destroy`.

```bash
export INFRAHUB_ADDRESS=http://localhost:8000
export INFRAHUB_API_TOKEN=06438eb2-8019-4776-878c-0941b1f1d1ec  # INFRAHUB_INITIAL_ADMIN_TOKEN in development/docker-compose.yml
until curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H 'Content-Type: application/json' \
    -d '{"query":"{ CoreNumberPool { edges { node { node_attribute { value } } } } }"}' \
    $INFRAHUB_ADDRESS/graphql/main | grep -q service_identifier; do sleep 5; done
uv run invoke dev.load-infra-data
```

3. In a second terminal, start a receiver that prints every payload it gets:

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

4. Log in at `http://localhost:8000` with the administrator account listed in `docs/docs/tutorials/getting-started/readme.mdx`, and create a webhook for every event on every branch (on Linux, use the host IP instead of `host.docker.internal`):

   - **GraphQL**: in the sandbox, run:

     ```graphql
     mutation {
       CoreStandardWebhookCreate(data: {
         name: {value: "qa-enrichment"}, branch_scope: {value: "all_branches"},
         url: {value: "http://host.docker.internal:8200/"},
         shared_key: {value: "qa-shared-key"}
       }) { ok }
     }
     ```

   - **Web interface** (alternative): open **Integrations > Webhooks**, add a standard webhook with the same name, URL, shared key and branch scope.

5. Update the description of any device and wait until its `infrahub.node.updated` event appears in `/tmp/qa-webhooks.jsonl`. Repeat if it does not arrive within a minute: the events sent just after a webhook is created can be missed, for longer while the workers still process the demo data load.

Every `jq` command below reads the last matching event. Filter on a value the step sets when earlier events of the same kind can match.

## Test Scenarios

### 1. A node update names the node and its new peer

**What this verifies**: an updated node's event carries its own labels, and a changed one-cardinality peer carries its labels.

**Steps, GraphQL path**:

- [ ] Run in the sandbox: `mutation { InfraDeviceUpdate(data: {hfid: ["atl1-edge1"], description: {value: "qa"}, platform: {hfid: ["Cisco NXOS SSH"]}}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraDevice" and .data.changelog.attributes.description.value=="qa") | .data.changelog | {display_label, hfid, platform: .relationships.platform}' /tmp/qa-webhooks.jsonl | tail -1`
- [ ] Confirm: `hfid` is `["atl1-edge1"]` and `display_label` is `atl1-edge1`.
- [ ] Confirm: `platform.peer_display_label` is `Cisco NXOS SSH`, `platform.peer_hfid` is `["Cisco NXOS SSH"]`, and the previous platform appears only as `peer_id_previous` / `peer_kind_previous`.

**Steps, web interface path**:

- [ ] Open device `atl1-edge2`, select **Edit**, set the description to `qa-ui` and pick another platform, then save.
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraDevice" and .data.changelog.attributes.description.value=="qa-ui") | .data.changelog | {display_label, hfid, platform: .relationships.platform}' /tmp/qa-webhooks.jsonl | tail -1`
- [ ] Confirm: `hfid` is `["atl1-edge2"]`, and `platform` carries the new platform's `peer_display_label` and `peer_hfid`.

**Expected result**: the device event names the device and its new platform without any ID lookup, whichever path saved it.

### 2. The peers on the other side of the change name the node

**What this verifies**: a peer whose schema lists the node back receives one event naming the node by its labels.

**Steps**:

- [ ] After the GraphQL path of scenario 1, run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraPlatform") | .data.changelog | {display_label, devices: [.relationships.devices.peers[] | {peer_display_label, peer_hfid, peer_status}]}' /tmp/qa-webhooks.jsonl | tail -4`
- [ ] Confirm: `Cisco NXOS SSH` has one event with `atl1-edge1` as peer: `peer_display_label` `atl1-edge1`, `peer_hfid` `["atl1-edge1"]`, `peer_status` `added`.
- [ ] Confirm: the previous platform of `atl1-edge1` has one event with the same device and `peer_status` `removed`.
- [ ] Confirm: the two platforms changed through the web interface path have the same pair of events for `atl1-edge2`.

**Expected result**: both platforms are told which device joined or left them, by name.

### 3. A many-cardinality relationship change names every peer

**What this verifies**: adding and removing peers of a many-cardinality relationship carries each peer's labels, and a peer that does not list the node back receives no event.

**Steps, GraphQL path**:

- [ ] Get two tag IDs: `query { BuiltinTag(limit: 2) { edges { node { id display_label } } } }`, and the ID of `atl1-edge1`.
- [ ] Run: `mutation { RelationshipAdd(data: {id: "<device-id>", name: "tags", nodes: [{id: "<tag1-id>"}, {id: "<tag2-id>"}]}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraDevice") | .data.changelog | {hfid, tags: [.relationships.tags.peers[] | {peer_display_label, peer_hfid, peer_status}]}' /tmp/qa-webhooks.jsonl | tail -1`
- [ ] Confirm: both tags are listed with `peer_display_label` set, `peer_hfid` `null` and `peer_status` `added`.
- [ ] Run: `jq -c 'select(.data.kind=="BuiltinTag")' /tmp/qa-webhooks.jsonl | tail -1` and confirm no event was delivered for the tags by this step.

**Steps, web interface path**:

- [ ] Open device `atl1-edge1`, open its **Tags** relationship tab, remove one tag and add another one.
- [ ] Run the same `jq` command as the GraphQL path, once per change.
- [ ] Confirm: the removed tag is listed with `peer_status` `removed` and the added tag with `peer_status` `added`, both with `peer_display_label` set.

**Expected result**: the device event names every tag it gained or lost, by its display label.

### 4. A branch merge delivers enriched node events

**What this verifies**: node events emitted by a merge carry the same fields as those of a mutation, whether the branch is merged directly or through a proposed change.

**Steps, GraphQL path**:

- [ ] Run: `mutation { BranchCreate(data: {name: "qa-merge"}) { ok } }`
- [ ] Open the sandbox on branch `qa-merge` and run the scenario 1 mutation with `description: {value: "qa-merge"}`.
- [ ] Run on `main`: `mutation { BranchMerge(data: {name: "qa-merge"}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .branch=="main" and .data.changelog.attributes.description.value=="qa-merge") | .data.changelog | {hfid, display_label}' /tmp/qa-webhooks.jsonl | tail -1`

**Steps, web interface path, branch merge**:

- [ ] Create branch `qa-merge-ui` from the branch selector.
- [ ] On `qa-merge-ui`, edit device `atl1-edge2` and set the description to `qa-merge-ui`.
- [ ] Open **Branches**, open `qa-merge-ui` and select **Merge**.
- [ ] Run the GraphQL path's `jq` command with the value `qa-merge-ui`.

**Steps, web interface path, proposed change**:

- [ ] Create branch `qa-pc` from the branch selector.
- [ ] On `qa-pc`, edit device `atl1-core1`, set the description to `qa-pc`, and add a tag in its **Tags** tab.
- [ ] Open **Proposed Changes**, create a proposed change from `qa-pc` to `main`, wait for its checks, approve it if approval is required, and select **Merge**.
- [ ] Run the GraphQL path's `jq` command with the value `qa-pc`, adding `tags: .relationships.tags` to the output.

**Expected result**: on every path, the event emitted on `main` for the device carries its `hfid` and display label, and the proposed change event also names the added tag with its `peer_display_label`.

### 5. A rebase delivers enriched node events

**What this verifies**: the node events a rebase emits on the rebased branch, for the changes made on that branch, carry the labels.

**Steps, GraphQL path**:

- [ ] Run: `mutation { BranchCreate(data: {name: "qa-rebase"}) { ok } }`
- [ ] Open the sandbox on branch `qa-rebase` and run: `mutation { InfraDeviceUpdate(data: {hfid: ["atl1-edge2"], description: {value: "qa-rebase"}}) { ok } }`
- [ ] On `main`, update the description of `atl1-core1`.
- [ ] Run: `mutation { BranchRebase(data: {name: "qa-rebase"}) { ok } }`
- [ ] Run: `jq -c 'select(.branch=="qa-rebase" and .event=="infrahub.node.updated") | .data.changelog | {node_kind, hfid, display_label}' /tmp/qa-webhooks.jsonl`

**Steps, web interface path**:

- [ ] Create branch `qa-rebase-ui`, and on it edit the description of `atl1-edge1` to `qa-rebase-ui`.
- [ ] On `main`, edit the description of `atl1-core2`.
- [ ] Open **Branches**, open `qa-rebase-ui` and select **Rebase**.
- [ ] Run the GraphQL path's `jq` command with the branch `qa-rebase-ui`.

**Expected result**: the rebase emits an event on the rebased branch for the device changed on it, with its `hfid` and display label. It emits no event on that branch for the device changed on `main`: a rebase emits events for the changes made on `main` only for the kinds whose schema the branch changed (`backend/infrahub/core/branch/tasks.py`, `rebase_branch`), and these branches change no schema.

### 6. The display label mutation publishes the full HFID

**What this verifies**: `InfrahubUpdateDisplayLabel` loads only the node's display label, and its event still carries the node's full HFID, including the part read through a relationship. The web interface does not send this mutation, so it has a GraphQL path only.

**Steps**:

- [ ] Get an interface of `atl1-edge1`: `query { InfraInterfaceL3(device__name__value: "atl1-edge1", limit: 1) { edges { node { id hfid } } } }`. Its `hfid` has two parts: the device name and the interface name.
- [ ] Run: `mutation { InfrahubUpdateDisplayLabel(data: {id: "<interface-id>", kind: "InfraInterfaceL3", value: "qa-label"}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraInterfaceL3" and .data.changelog.display_label=="qa-label") | .data.changelog | {display_label, hfid}' /tmp/qa-webhooks.jsonl | tail -1`

**Expected result**: `display_label` is `qa-label`, and `hfid` is the two-part HFID the query returned.

### 7. The computed attribute mutation publishes the full HFID

**What this verifies**: `InfrahubUpdateComputedAttribute` loads only the attribute it sets, and its event still carries the node's full HFID. The web interface does not send this mutation, so it has a GraphQL path only.

**Steps**:

- [ ] Run: `mutation { InfrahubUpdateComputedAttribute(data: {id: "<atl1-edge1-id>", kind: "InfraDevice", attribute: "computed_description", value: "qa-computed"}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraDevice" and .data.changelog.attributes.computed_description.value=="qa-computed") | .data.changelog | {hfid, computed_description: .attributes.computed_description.value}' /tmp/qa-webhooks.jsonl | tail -1`

**Expected result**: `computed_description` is `qa-computed`, and `hfid` is `["atl1-edge1"]`, not an empty list. `computed_description` is a Jinja2 computed attribute (`models/base/dcim.yml`), so its automation can recompute it and emit another event right after; the `jq` filter selects the event of this step.

### 8. A relationship that feeds the display label

**What this verifies**: after a change of a relationship that the display label reads, the event carries the display label computed from the new peer, not the value stored before the change.

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
uv run infrahubctl schema load /tmp/qa_shirt_schema.yml
```

- [ ] Create two colors and a shirt without a color: `mutation { r: TestingColorCreate(data: {name: {value: "red"}}) { object { id } } b: TestingColorCreate(data: {name: {value: "blue"}}) { object { id } } TestingShirtCreate(data: {name: {value: "polo"}}) { object { id } } }`

**GraphQL path** (`RelationshipAdd` accepts a cardinality-one relationship that has no peer yet):

- [ ] Run: `mutation { RelationshipAdd(data: {id: "<shirt-id>", name: "color", nodes: [{id: "<red-id>"}]}) { ok } }`
- [ ] Run: `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="TestingShirt") | .data.changelog | {display_label, hfid}' /tmp/qa-webhooks.jsonl | tail -1`
- [ ] Confirm: `display_label` is `polo red` and `hfid` is `["polo"]`.

**Web interface path** (the form saves through the node update mutation):

- [ ] Open shirt `polo`, select **Edit**, change the color to `blue`, then save.
- [ ] Run the same `jq` command.
- [ ] Confirm: `display_label` is `polo blue` and `hfid` is `["polo"]`.

**Expected result**: the shirt event shows the display label that the new color gives it.

## Edge Cases

- [ ] Kind without an HFID: in the web interface, create an IP address in **IPAM > IP Addresses** → run `jq -c 'select(.event=="infrahub.node.created" and .data.kind=="IpamIPAddress") | .data.changelog | {hfid, display_label}' /tmp/qa-webhooks.jsonl | tail -1` and confirm `hfid` is `null` and `display_label` is the address.
- [ ] HFID change: in the web interface, rename device `atl1-edge2` to `atl1-edge2-qa` → run `jq -c 'select(.event=="infrahub.node.updated" and .data.kind=="InfraDevice") | .data.changelog | {hfid, display_label}' /tmp/qa-webhooks.jsonl | tail -1` and confirm `hfid` is `["atl1-edge2-qa"]`.
- [ ] Cascade delete: in the web interface, delete device `atl1-core2` → its interfaces are deleted with it. Count the deliveries with `jq -c 'select(.event=="infrahub.node.deleted")' /tmp/qa-webhooks.jsonl | wc -l` until the count stops growing (deliveries go out at a few per second, so a device with many interfaces takes minutes), then open **Tasks** and confirm that no webhook delivery failed.

## Teardown

`dev.destroy` removes the containers and their volumes, including the database. Skip it to keep the stack.

```bash
uv run invoke dev.destroy
rm -f /tmp/qa_receiver.py /tmp/qa-webhooks.jsonl /tmp/qa_shirt_schema.yml
```

Stop the receiver with Ctrl+C.

## Sign-off

- [ ] All scenarios above pass, on every path.
- [ ] No unexpected output, warnings, or errors observed.
- [ ] Tester: ______________________  Date: __________
