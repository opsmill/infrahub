# QA Checklist — Selective regeneration after a merge, part 2

**Generated**: 2026-09-30 22:00 local
**Feature**: dev/specs/ifc-2950-selective-regen-part2 (Epic IFC-2950, changes merged into `develop` after 1.11.0)
**Source**: speckit.opsmill.qa

## Scope

Verify that, after a merge, Infrahub regenerates only the artifacts of the targets whose data changed, when the artifact's query reads that data through a relationship (IFC-2946) or through a related object's display label (IFC-3098). Also verify that it still regenerates every target when it cannot trace a change back to specific targets. Out of scope: the bug fixes of this Epic (IFC-2907, IFC-2996, IFC-3071, IFC-3251), which are covered by automated tests, and the internal refactors (IFC-2916, IFC-3067, IFC-3070), which have no visible change.

## Prerequisites

- [ ] A checkout of `develop` that includes the IFC-2950 merges (`git merge-base --is-ancestor 22173ff49 HEAD && echo ok` prints `ok`).
- [ ] Docker running, `uv sync --all-groups` completed.
- [ ] A GitHub account that can create a repository and a Personal Access Token for it.
- [ ] `infrahubctl` configured against the local instance (`invoke demo.cli-git` opens a shell that has it).

## Setup

```bash
export INFRAHUB_IMAGE_VER=local
uv run invoke dev.build
uv run invoke demo.start
uv run invoke demo.load-infra-schema
uv run invoke demo.load-infra-data
```

The demo data has 10 devices in the `edge_router` group, two per site (`atl1`, `ord1`, `jfk1`, `den1`, `dfw1`).

Create a GitHub repository `qa-selective-regen` with these three files:

- `.infrahub.yml`

  ```yaml
  queries:
    - name: qa_device
      file_path: qa_device.gql
  jinja2_transforms:
    - name: qa_device
      query: qa_device
      template_path: qa_device.j2
  artifact_definitions:
    - name: QA device config
      artifact_name: qa-device-config
      parameters:
        device: name__value
      content_type: text/plain
      targets: edge_router
      transformation: qa_device
  ```

- `qa_device.gql`

  ```graphql
  query qa_device($device: String!) {
    InfraDevice(name__value: $device) {
      edges { node {
        name { value }
        site { node { display_label } }
        interfaces { edges { node { name { value } description { value } } } }
      } }
    }
  }
  ```

- `qa_device.j2`

  ```jinja
  {% set d = data.InfraDevice.edges[0].node %}hostname {{ d.name.value }} site {{ d.site.node.display_label }}
  {% for i in d.interfaces.edges %}{{ i.node.name.value }}: {{ i.node.description.value }}
  {% endfor %}
  ```

Add it in the UI under **Integrations > Git Repositories** and wait until the **Artifacts** page lists 10 `qa-device-config` artifacts.

## Test Scenarios

### 1. The test query is single-target

**What this verifies**: the query qualifies for selective regeneration.

**Steps**:

- [ ] Run: `infrahubctl graphql query-report qa_device --online`
- [ ] Observe: `Targets unique nodes: true`

**Expected result**: the report shows `true`. If it shows `false`, the other scenarios regenerate every target and cannot be evaluated.

### 2. A change reached through a relationship regenerates one device

**What this verifies**: changing one interface regenerates only the artifact of the device that has it (IFC-2946).

**Steps**:

- [ ] Create a branch `qa-interface`. On it, change the description of interface `Ethernet1` of device `atl1-edge1`.
- [ ] Merge the branch into `main` from the UI.
- [ ] Open **Tasks** and count the `Generate artifact qa-device-config` tasks started after the merge.
- [ ] Open the `qa-device-config` artifact of `atl1-edge1` and of `ord1-edge1`.

**Expected result**: one `Generate artifact qa-device-config` task. The artifact of `atl1-edge1` shows the new description; the artifact of `ord1-edge1` is unchanged.

### 3. Renaming a site regenerates only the devices at that site

**What this verifies**: a change behind a related object's display label regenerates only the targets that show it (IFC-3098).

**Steps**:

- [ ] Create a branch `qa-site`. On it, rename site `atl1` to `atl9`.
- [ ] Merge the branch into `main`.
- [ ] Count the `Generate artifact qa-device-config` tasks started after the merge.

**Expected result**: two tasks, for `atl1-edge1` and `atl1-edge2`. Both artifacts show `site atl9`; the artifacts of the other 8 devices are unchanged.

### 4. A change that cannot be traced back regenerates every device

**What this verifies**: Infrahub still regenerates every target when it cannot identify the affected ones.

**Steps**:

- [ ] In `qa_device.gql`, add `... on InfraInterfaceL3 { ip_addresses { edges { node { address { value } } } } }` inside the interface `node`, and commit to `main`. Wait for the repository to sync.
- [ ] Create a branch `qa-ip`. On it, change the address of one IP address assigned to an interface of `atl1-edge1`.
- [ ] Open a proposed change for `qa-ip`, open its artifact check task, then merge it.
- [ ] Count the `Generate artifact qa-device-config` tasks started after the merge.

**Expected result**: 10 tasks, one per device. The artifact check task log contains `All targets will be processed.`

## Edge Cases

- [ ] Group change: add a device to `edge_router` on a branch and merge → one new `qa-device-config` artifact; the other 10 are not regenerated.
- [ ] Two interfaces on two devices at different sites changed in one branch → exactly two tasks after the merge.
- [ ] `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE=false` on the server, repeat scenario 2 → 10 tasks.

## Teardown

```bash
uv run invoke demo.destroy
```

Delete the `qa-selective-regen` GitHub repository and its Personal Access Token.

## Sign-off

- [ ] All scenarios above pass.
- [ ] No unexpected output, warnings, or errors observed.
- [ ] Tester: ______________________  Date: __________
