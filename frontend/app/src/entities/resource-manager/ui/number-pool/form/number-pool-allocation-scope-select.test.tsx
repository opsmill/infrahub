import React from "react";
import { describe, expect, test } from "vitest";
import { userEvent } from "vitest/browser";

import { render } from "../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { NumberPoolAllocationScopeSelect } from "./number-pool-allocation-scope-select";

const unitIdAttribute = generateAttributeSchema({
  name: "unit_id",
  label: "Unit ID",
  kind: "Number",
  optional: false,
});

const vlanIdAttribute = generateAttributeSchema({
  name: "vlan_id",
  label: "VLAN ID",
  kind: "Number",
  unique: true,
});

const SCHEMA = generateNodeSchema({
  kind: "InfraSubinterface",
  label: "Subinterface",
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text", optional: false }),
    unitIdAttribute,
    vlanIdAttribute,
  ],
  relationships: [
    generateRelationshipSchema({
      name: "device",
      label: "Device",
      cardinality: "one",
      optional: false,
    }),
    generateRelationshipSchema({
      name: "site",
      label: "Site",
      cardinality: "one",
      optional: false,
    }),
  ],
});

function AllocationScopeSelect({ defaultValue = [] }: { defaultValue?: Array<string> }) {
  const [value, setValue] = React.useState(defaultValue);
  return (
    <NumberPoolAllocationScopeSelect
      schema={SCHEMA}
      attribute={unitIdAttribute}
      value={value}
      onChange={setValue}
    />
  );
}

const addButton = (component: Awaited<ReturnType<typeof render>>) =>
  component.getByRole("button", { name: /^Add (a relationship or attribute|another)$/ });

// The field's own border, outside the add button and the picked fields.
const FIELD_EDGE = { position: { x: 1, y: 1 } };

describe("NumberPoolAllocationScopeSelect", () => {
  test("does not open the list when the empty field is clicked outside the add button", async () => {
    // GIVEN
    const component = await render(<AllocationScopeSelect />);

    // WHEN
    await component.getByRole("group").click(FIELD_EDGE);

    // THEN
    expect(component.getByRole("listbox").query()).toBeNull();
  });

  test("disables the field and explains why when the attribute is unique", async () => {
    // WHEN
    const component = await render(
      <NumberPoolAllocationScopeSelect
        schema={SCHEMA}
        attribute={vlanIdAttribute}
        value={[]}
        onChange={() => {}}
      />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "No scope" })).toBeDisabled();
    await expect
      .element(
        component.getByText("VLAN ID is unique across all nodes, so it cannot have a scope.")
      )
      .toBeVisible();
  });

  test("disables the field when no field of the node can scope the pool", async () => {
    // GIVEN
    const circuitSchema = generateNodeSchema({
      kind: "InfraCircuit",
      label: "Circuit",
      attributes: [
        unitIdAttribute,
        generateAttributeSchema({ name: "description", label: "Description", kind: "Text" }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "endpoints",
          label: "Endpoints",
          cardinality: "many",
          optional: false,
        }),
      ],
    });

    // WHEN
    const component = await render(
      <NumberPoolAllocationScopeSelect
        schema={circuitSchema}
        attribute={unitIdAttribute}
        value={[]}
        onChange={() => {}}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: "No relationship or attribute eligible" }))
      .toBeDisabled();
  });

  test("hides the add button while every field is picked, and shows it again once one is removed", async () => {
    // GIVEN
    const component = await render(
      <AllocationScopeSelect defaultValue={["name", "device", "site"]} />
    );
    await expect.poll(() => addButton(component).query()).toBeNull();

    // WHEN
    await component.getByRole("row", { name: "Device" }).getByRole("button").click();

    // THEN
    await expect.element(addButton(component)).toBeVisible();
    await expect
      .element(component.getByRole("grid", { name: "Scoped by" }))
      .toHaveTextContent("Name");
  });

  test("keeps the list open so several fields can be picked in a row", async () => {
    // GIVEN
    const component = await render(<AllocationScopeSelect />);
    await addButton(component).click();

    // WHEN
    await component.getByRole("option", { name: "Name" }).click();
    await component.getByRole("option", { name: "Device" }).click();
    await userEvent.keyboard("{Escape}");

    // THEN
    const allocationScope = component.getByRole("grid", { name: "Scoped by" });
    await expect.element(allocationScope).toHaveTextContent("Name");
    await expect.element(allocationScope).toHaveTextContent("Device");
  });

  test("goes from a picked field straight to the add button, skipping its remove button", async () => {
    // GIVEN
    const component = await render(<AllocationScopeSelect defaultValue={["device"]} />);
    await component.getByRole("row", { name: "Device" }).click();

    // WHEN
    await userEvent.tab();

    // THEN
    await expect.element(addButton(component)).toHaveFocus();
  });

  test("moves focus to the add button once the last picked field is removed", async () => {
    // GIVEN
    const component = await render(<AllocationScopeSelect defaultValue={["device"]} />);
    await component.getByRole("row", { name: "Device" }).click();

    // WHEN
    await userEvent.keyboard("{Delete}");

    // THEN
    await expect.element(addButton(component)).toHaveFocus();
    await expect.poll(() => component.getByRole("grid", { name: "Scoped by" }).query()).toBeNull();
  });
});
