import { beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { OBJECT_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { ObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateGenericSchema,
  generateNodeSchema,
} from "../../../../../../tests/fake/schema";
import { ObjectTableSchemaSelector } from "./object-table-schema-selector";

const deviceSchema = generateNodeSchema({
  kind: "InfraDevice",
  name: "Device",
  label: "Device",
  hash: "device-hash",
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
    generateAttributeSchema({ name: "serial", label: "Serial", kind: "Text" }),
  ],
  relationships: [],
});

const virtualMachineSchema = generateNodeSchema({
  kind: "InfraVirtualMachine",
  name: "VirtualMachine",
  label: "Virtual Machine",
  hash: "virtual-machine-hash",
  attributes: [generateAttributeSchema({ name: "name", label: "Name", kind: "Text" })],
  relationships: [],
});

const endpointGeneric = generateGenericSchema({
  kind: "InfraEndpoint",
  name: "Endpoint",
  label: "Endpoint",
  hash: "endpoint-hash",
  used_by: [deviceSchema.kind!, virtualMachineSchema.kind!],
  attributes: [generateAttributeSchema({ name: "name", label: "Name", kind: "Text" })],
  relationships: [],
});

const seedUrl = (search: string) =>
  window.history.replaceState(null, "", `${window.location.pathname}?${search}`);

const paramInUrl = (name: string) => new URLSearchParams(window.location.search).get(name);

/**
 * The one param a selection always rewrites, whichever kind was picked: the write that prunes the
 * filters carries any column clearing with it, so waiting on the pruning is what makes an assertion
 * about the column params read the settled URL rather than the one still on its way out.
 */
const STALE_FILTER_IN_URL = `filters=${encodeURIComponent('[{"name":"gone_from_this_schema__value","value":"core"}]')}`;
const isStaleFilterPruned = () => !(paramInUrl("filters") ?? "").includes("gone_from_this_schema");

const renderSelector = (selectedSchema: ModelSchema = deviceSchema) =>
  render(
    <ObjectTableContext
      value={{
        filters: [],
        setFilters: vi.fn(),
        baseSchema: endpointGeneric,
        selectedSchema,
        permission: PERMISSION_ALLOW_ALL,
        columnSurface: OBJECT_COLUMN_SURFACE,
        supportsColumnVisibility: true,
      }}
    >
      <ObjectTableSchemaSelector />
    </ObjectTableContext>
  );

describe("ObjectTableSchemaSelector", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
    store.set(nodeSchemasAtom, [deviceSchema, virtualMachineSchema]);
    store.set(genericSchemasAtom, [endpointGeneric]);
  });

  test("clears the column params when switching to another kind", async () => {
    // GIVEN column choices made under `InfraDevice`, `serial` being a column only that kind has.
    seedUrl("kind=InfraDevice&hide_columns=serial&show_columns=name");
    const component = await renderSelector();

    // WHEN
    await component.getByTestId("object-schema-schema-selector").click();
    await component.getByRole("option", { name: /Virtual Machine/ }).click();

    // THEN the new kind starts from its own defaults instead of inheriting — or later silently
    // destroying — names it has no column for.
    await expect.poll(() => paramInUrl("kind")).toBe("InfraVirtualMachine");
    expect(paramInUrl("hide_columns")).toBeNull();
    expect(paramInUrl("show_columns")).toBeNull();
  });

  test("clears the column params when switching back to the generic", async () => {
    // GIVEN
    seedUrl("kind=InfraDevice&hide_columns=serial&show_columns=name");
    const component = await renderSelector();

    // WHEN
    await component.getByTestId("object-schema-schema-selector").click();
    await component.getByRole("option", { name: /All Endpoint/ }).click();

    // THEN
    await expect.poll(() => paramInUrl("kind")).toBeNull();
    expect(paramInUrl("hide_columns")).toBeNull();
    expect(paramInUrl("show_columns")).toBeNull();
  });

  test("keeps the column params when re-selecting the kind already in view", async () => {
    // GIVEN
    seedUrl(`kind=InfraDevice&hide_columns=serial&show_columns=name&${STALE_FILTER_IN_URL}`);
    const component = await renderSelector();

    // WHEN
    await component.getByTestId("object-schema-schema-selector").click();
    await component.getByRole("option", { name: /Device/ }).click();

    // THEN the schema never changed, so there is nothing to protect the user's choices from.
    await expect.poll(isStaleFilterPruned).toBe(true);
    expect(paramInUrl("hide_columns")).toBe("serial");
    expect(paramInUrl("show_columns")).toBe("name");
  });

  test("keeps the column params when re-selecting the generic already in view", async () => {
    // GIVEN column choices made while the base schema is the one on screen.
    seedUrl(`hide_columns=name&${STALE_FILTER_IN_URL}`);
    const component = await renderSelector(endpointGeneric);

    // WHEN
    await component.getByTestId("object-schema-schema-selector").click();
    await component.getByRole("option", { name: /All Endpoint/ }).click();

    // THEN
    await expect.poll(isStaleFilterPruned).toBe(true);
    expect(paramInUrl("hide_columns")).toBe("name");
    expect(paramInUrl("kind")).toBeNull();
  });
});
