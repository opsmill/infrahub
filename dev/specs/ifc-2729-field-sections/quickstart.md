# Quickstart: view field sections on the demo schema

The demo schema `models/base/dcim.yml` declares LACP, Layer 2 and Layer 3 sections on the
`InfraLagInterface` generic. Run the commands from the repository root.

## Load the demo

```bash
uv run invoke dev.start
uv run invoke dev.load-infra-schema
uv run invoke dev.load-infra-data
```

The schema and the demo data load without error.

## What to look at in the web interface

1. Open an `InfraLagInterfaceL2` object, for example `port-channel1` of `atl1-leaf1`. The detail
   page shows, in this order:
   - Details, with the fields without a container, including MaxBundle.
   - LACP (LACP, Minimum links and the `mlag` relationship), with "Link aggregation settings"
     under the title.
   - Layer 2 (Layer2 Mode, Untagged VLAN, Tagged VLANs).

   No Layer 3 card is shown, because this node has no field in Layer 3.
2. Select the Layer 2 header: the card collapses. Select it again: it expands.
3. Select Edit: the form shows Details, LACP and Layer 2 panels, all expanded. Change
   Minimum links and save: the LACP card shows the new value.
4. Open the `InfraLagInterfaceL3` list and select New: the form shows Details, LACP and Layer 3 (MTU)
   panels. Save an object and open it: the Layer 3 card starts collapsed and shows MTU
   `1500`; no Layer 2 card is shown.
5. Open Schema in the sidebar and select `InfraLagInterface`: the Containers block lists `lacp`,
   `layer2` and `layer3`, and the `lacp` attribute shows `Container: lacp`.
6. Open an object of a kind without containers, such as an `InfraDevice`: the detail page shows
   the single Details card and the edit form is a flat list.

## Run the tests

```bash
uv run pytest backend/tests/unit/core/schema backend/tests/unit/api/test_schema_load_contract.py
uv run pytest backend/tests/component/api/test_40_schema.py \
  backend/tests/component/core/schema_manager/test_manager_schema.py \
  backend/tests/component/core/schema/schema_branch/test_process_idempotency.py
uv run pytest backend/tests/integration/schema_lifecycle/test_schema_containers_branch_merge.py
cd frontend/app && pnpm test src/entities/nodes/object src/entities/schema \
  src/shared/components/form src/pages/ipam
```

The component and integration tests need a running Docker daemon.
