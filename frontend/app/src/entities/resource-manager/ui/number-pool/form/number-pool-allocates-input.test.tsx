import { beforeEach, describe, expect, test } from "vitest";
import { userEvent } from "vitest/browser";

import { store } from "@/shared/stores";

import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { NumberPoolAllocatesInput } from "./number-pool-allocates-input";

const subinterfaceSchema = generateNodeSchema({
  kind: "InfraSubinterface",
  name: "Subinterface",
  namespace: "Infra",
  label: "Subinterface",
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text", optional: false }),
    generateAttributeSchema({
      name: "unit_id",
      label: "Unit ID",
      kind: "Number",
      optional: false,
      parameters: { min_value: 0, max_value: 16_383 },
    }),
    generateAttributeSchema({ name: "vlan_id", label: "VLAN ID", kind: "Number", unique: true }),
    generateAttributeSchema({
      name: "computed_id",
      label: "Computed ID",
      kind: "Number",
      read_only: true,
    }),
    generateAttributeSchema({
      name: "description",
      label: "Description",
      kind: "Text",
      optional: true,
    }),
  ],
  relationships: [
    generateRelationshipSchema({
      name: "device",
      label: "Device",
      cardinality: "one",
      optional: false,
    }),
    generateRelationshipSchema({
      name: "tags",
      label: "Tags",
      cardinality: "many",
      optional: true,
    }),
  ],
});

const tagSchema = generateNodeSchema({ kind: "BuiltinTag", label: "Tag" });

const renderAllocatesInput = () =>
  render(
    <TestForm
      defaultValues={{
        node: { value: "" },
        node_attribute: { value: "" },
        allocation_scope: { value: [] },
      }}
    >
      <NumberPoolAllocatesInput />
    </TestForm>
  );

describe("NumberPoolAllocatesInput", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [subinterfaceSchema, tagSchema]);
    store.set(genericSchemasAtom, []);
  });

  test("asks for a node before showing its attribute and allocation scope", async () => {
    // WHEN
    const component = await renderAllocatesInput();

    // THEN
    await expect
      .element(component.getByText("Pick a node to choose its attribute and scope."))
      .toBeVisible();
    await expect
      .poll(() => component.getByRole("button", { name: /Attribute$/ }).query())
      .toBeNull();
  });

  test("lists only nodes with a number attribute a pool can assign", async () => {
    // GIVEN
    const component = await renderAllocatesInput();

    // WHEN
    await component.getByRole("button", { name: "Node" }).click();

    // THEN
    await expect.element(component.getByRole("option", { name: /Subinterface/ })).toBeVisible();
    await expect.poll(() => component.getByRole("option", { name: /Tag/ }).query()).toBeNull();
  });

  test("tells the user that nodes without a number attribute are not listed", async () => {
    // GIVEN
    const component = await renderAllocatesInput();

    // WHEN
    await component.getByRole("button", { name: "Node" }).click();

    // THEN
    await expect
      .element(component.getByText("Only nodes with an editable Number attribute are listed."))
      .toBeVisible();
  });

  test("lists the node's number attributes that are not read-only, with their limits", async () => {
    // GIVEN
    const component = await renderAllocatesInput();
    await component.getByRole("button", { name: "Node" }).click();
    await component.getByRole("option", { name: /Subinterface/ }).click();

    // WHEN
    await component.getByRole("button", { name: /Attribute$/ }).click();

    // THEN
    await expect
      .element(component.getByRole("option", { name: /Unit ID/ }))
      .toHaveTextContent("0 – 16,383");
    await expect
      .element(component.getByRole("option", { name: /VLAN ID/ }))
      .toHaveTextContent("Unique");
    await expect
      .poll(() => component.getByRole("option", { name: /Computed ID/ }).query())
      .toBeNull();
  });

  test("offers only the fields that can scope the pool", async () => {
    // GIVEN
    const component = await renderAllocatesInput();
    await component.getByRole("button", { name: "Node" }).click();
    await component.getByRole("option", { name: /Subinterface/ }).click();
    await component.getByRole("button", { name: /Attribute$/ }).click();
    await component.getByRole("option", { name: /Unit ID/ }).click();

    // WHEN
    await component.getByRole("button", { name: "Add a relationship or attribute" }).click();

    // THEN
    await expect.element(component.getByRole("option", { name: "Device" })).toBeVisible();
    await expect.element(component.getByRole("option", { name: "Name" })).toBeVisible();
    await expect.poll(() => component.getByRole("option", { name: "Unit ID" }).query()).toBeNull();
    await expect
      .poll(() => component.getByRole("option", { name: "Description" }).query())
      .toBeNull();
    await expect.poll(() => component.getByRole("option", { name: "Tags" }).query()).toBeNull();
  });

  test("disables the allocation scope and clears it when the attribute is unique", async () => {
    // GIVEN
    const component = await renderAllocatesInput();
    await component.getByRole("button", { name: "Node" }).click();
    await component.getByRole("option", { name: /Subinterface/ }).click();
    await component.getByRole("button", { name: /Attribute$/ }).click();
    await component.getByRole("option", { name: /Unit ID/ }).click();
    await component.getByRole("button", { name: "Add a relationship or attribute" }).click();
    await component.getByRole("option", { name: "Device" }).click();
    await userEvent.keyboard("{Escape}");

    // WHEN
    await component.getByRole("button", { name: /Attribute$/ }).click();
    await component.getByRole("option", { name: /VLAN ID/ }).click();

    // THEN
    await expect
      .element(
        component.getByText("VLAN ID is unique across all nodes, so it cannot have a scope.")
      )
      .toBeVisible();
    await expect.element(component.getByRole("button", { name: "No scope" })).toBeDisabled();
    await expect.poll(() => component.getByRole("grid", { name: "Scoped by" }).query()).toBeNull();
  });

  test("drops the new attribute from the allocation scope, because a pool cannot be scoped by the attribute it allocates", async () => {
    // GIVEN
    const cardSchema = generateNodeSchema({
      kind: "InfraLineCard",
      label: "Line card",
      attributes: [
        generateAttributeSchema({
          name: "unit_id",
          label: "Unit ID",
          kind: "Number",
          optional: false,
        }),
        generateAttributeSchema({
          name: "slot_id",
          label: "Slot ID",
          kind: "Number",
          optional: false,
        }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "device",
          label: "Device",
          cardinality: "one",
          optional: false,
        }),
      ],
    });
    store.set(nodeSchemasAtom, [cardSchema]);
    const component = await renderAllocatesInput();
    await component.getByRole("button", { name: "Node" }).click();
    await component.getByRole("option", { name: /Line card/ }).click();
    await component.getByRole("button", { name: /Attribute$/ }).click();
    await component.getByRole("option", { name: /Unit ID/ }).click();
    // Both lists offer Slot ID, so each one must finish closing before the other opens.
    await expect.poll(() => component.getByRole("listbox").query()).toBeNull();
    await component.getByRole("button", { name: "Add a relationship or attribute" }).click();
    await component.getByRole("option", { name: "Slot ID" }).click();
    await component.getByRole("option", { name: "Device" }).click();
    await userEvent.keyboard("{Escape}");
    await expect.poll(() => component.getByRole("listbox").query()).toBeNull();

    // WHEN
    await component.getByRole("button", { name: /Attribute$/ }).click();
    await component.getByRole("option", { name: /Slot ID/ }).click();

    // THEN
    const allocationScope = component.getByRole("grid", { name: "Scoped by" });
    await expect.element(allocationScope).toHaveTextContent("Device");
    await expect.element(allocationScope).not.toHaveTextContent("Slot ID");
  });

  test("clears the attribute and the allocation scope when the node changes", async () => {
    // GIVEN
    const otherSchema = generateNodeSchema({
      kind: "InfraCircuit",
      label: "Circuit",
      attributes: [
        generateAttributeSchema({
          name: "circuit_number",
          label: "Circuit number",
          kind: "Number",
        }),
      ],
      relationships: [],
    });
    store.set(nodeSchemasAtom, [subinterfaceSchema, otherSchema]);
    const component = await renderAllocatesInput();
    await component.getByRole("button", { name: "Node" }).click();
    await component.getByRole("option", { name: /Subinterface/ }).click();
    await component.getByRole("button", { name: /Attribute$/ }).click();
    await component.getByRole("option", { name: /Unit ID/ }).click();

    // WHEN
    await component.getByRole("button", { name: "Node" }).click();
    await component.getByRole("option", { name: /Circuit/ }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: /Attribute$/ }))
      .toHaveTextContent("Select an attribute");
    await expect
      .poll(() => component.getByRole("button", { name: "Scoped by" }).query())
      .toBeNull();
  });

  test("shows what a saved pool allocates as text, with one line per allocation scope field, because it is fixed once the pool exists", async () => {
    // WHEN
    const component = await render(
      <TestForm
        defaultValues={{
          node: { value: "InfraSubinterface" },
          node_attribute: { value: "unit_id" },
          allocation_scope: { value: ["device", "missing_field"] },
        }}
      >
        <NumberPoolAllocatesInput isReadOnly />
      </TestForm>
    );

    // THEN
    await expect.element(component.getByText("Subinterface")).toBeVisible();
    await expect.element(component.getByText("Unit ID")).toBeVisible();
    const allocationScope = component.getByRole("list", { name: "Scoped by" });
    await expect.element(allocationScope.getByRole("listitem").nth(0)).toHaveTextContent("Device");
    await expect
      .element(allocationScope.getByRole("listitem").nth(1))
      .toHaveTextContent("missing_field");
    await expect.poll(() => component.getByRole("button", { name: "Node" }).query()).toBeNull();
  });

  test("says when a saved pool has no allocation scope", async () => {
    // WHEN
    const component = await render(
      <TestForm
        defaultValues={{
          node: { value: "InfraSubinterface" },
          node_attribute: { value: "unit_id" },
          allocation_scope: { value: [] },
        }}
      >
        <NumberPoolAllocatesInput isReadOnly />
      </TestForm>
    );

    // THEN
    await expect.element(component.getByText("No scope")).toBeVisible();
  });
});
