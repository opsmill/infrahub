import { createRef } from "react";
import { afterAll, beforeAll, describe, expect, test } from "vitest";

import type { FormRef } from "@/shared/components/ui/form";
import { store } from "@/shared/stores";

import { ScopeField } from "@/entities/resource-manager/ui/number-pool-form/scope-field";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateGenericSchema,
  generateNodeSchema,
} from "../../../../../tests/fake/schema";

const baseRelationship = generateNodeSchema().relationships![0]!;

const relationship = (overrides: Partial<RelationshipSchema>): RelationshipSchema => ({
  ...baseRelationship,
  kind: "Generic",
  ...overrides,
});

const subinterfaceSchema = generateNodeSchema({
  id: "subinterface",
  kind: "InfraSubinterface",
  name: "Subinterface",
  namespace: "Infra",
  label: "Subinterface",
  attributes: [
    generateAttributeSchema({ name: "unit_id", label: "Unit ID", kind: "Number", optional: false }),
    generateAttributeSchema({ name: "vlan_id", label: "VLAN ID", kind: "Number", optional: false }),
    generateAttributeSchema({
      name: "description",
      label: "Description",
      kind: "Text",
      optional: true,
    }),
  ],
  relationships: [
    relationship({
      name: "device",
      label: "Device",
      peer: "InfraDevice",
      cardinality: "one",
      optional: false,
    }),
    relationship({
      name: "untagged_vlan",
      label: "Untagged VLAN",
      peer: "InfraVLAN",
      cardinality: "one",
      optional: true,
    }),
  ],
});

const circuitSchema = generateNodeSchema({
  id: "circuit",
  kind: "InfraCircuit",
  name: "Circuit",
  namespace: "Infra",
  label: "Circuit",
  attributes: [
    generateAttributeSchema({
      name: "circuit_number",
      label: "Circuit number",
      kind: "Number",
      optional: false,
      unique: true,
    }),
  ],
  relationships: [
    relationship({
      name: "provider",
      label: "Provider",
      peer: "OrganizationProvider",
      cardinality: "one",
      optional: false,
    }),
  ],
});

const tagSchema = generateNodeSchema({
  id: "tag",
  kind: "BuiltinTag",
  name: "Tag",
  namespace: "Builtin",
  label: "Tag",
  attributes: [
    generateAttributeSchema({ name: "weight", label: "Weight", kind: "Number", optional: false }),
    generateAttributeSchema({ name: "note", label: "Note", kind: "Text", optional: true }),
  ],
  relationships: [],
});

const endpointGeneric = generateGenericSchema({
  id: "endpoint",
  kind: "InfraEndpoint",
  name: "Endpoint",
  namespace: "Infra",
  label: "Endpoint",
  attributes: [
    generateAttributeSchema({ name: "port", label: "Port", kind: "Number", optional: false }),
  ],
  relationships: [
    relationship({
      name: "site",
      label: "Site",
      peer: "LocationSite",
      cardinality: "one",
      optional: false,
    }),
  ],
});

const userValue = (value: string) => ({ source: { type: "user" }, value });

function renderScopeField(node: string | null, attribute: string, scope: string[] = []) {
  const formRef = createRef<FormRef>();
  const defaultValues = {
    ...(node && { node: userValue(node) }),
    node_attribute: userValue(attribute),
    allocation_scope: scope,
  };
  const rendered = render(
    <TestForm ref={formRef} defaultValues={defaultValues}>
      <ScopeField />
    </TestForm>
  );
  return { formRef, rendered };
}

describe("ScopeField", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);
  const initialGenericSchemas = store.get(genericSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [subinterfaceSchema, circuitSchema, tagSchema]);
    store.set(genericSchemasAtom, [endpointGeneric]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
    store.set(genericSchemasAtom, initialGenericSchemas);
  });

  test("cannot be opened before a node is chosen", async () => {
    // GIVEN
    const { rendered } = renderScopeField(null, "");

    // WHEN
    const component = await rendered;

    // THEN
    await expect
      .element(component.getByRole("button", { name: "No relationship or attribute" }))
      .toBeDisabled();
  });

  test("lists the fields of the node, with the reason next to each field that cannot be chosen", async () => {
    // GIVEN
    const component = await renderScopeField("InfraSubinterface", "unit_id").rendered;

    // WHEN
    await component.getByRole("button", { name: "No relationship or attribute" }).click();

    // THEN
    const device = component.getByRole("option", { name: /^Device/ });
    await expect.element(device).toHaveTextContent("InfraDevice");
    await expect.element(device).not.toHaveAttribute("aria-disabled", "true");
    const vlanId = component.getByRole("option", { name: /^VLAN ID/ });
    await expect.element(vlanId).not.toHaveAttribute("aria-disabled", "true");

    const untaggedVlan = component.getByRole("option", { name: /^Untagged VLAN/ });
    await expect.element(untaggedVlan).toHaveTextContent("Optional");
    await expect.element(untaggedVlan).toHaveAttribute("aria-disabled", "true");
    const description = component.getByRole("option", { name: /^Description/ });
    await expect.element(description).toHaveAttribute("aria-disabled", "true");
    const unitId = component.getByRole("option", { name: /^Unit ID/ });
    await expect.element(unitId).toHaveTextContent("This is the attribute the pool allocates");
    await expect.element(unitId).toHaveAttribute("aria-disabled", "true");
  });

  test("stores the chosen fields as bare field names and shows them in order", async () => {
    // GIVEN
    const { formRef, rendered } = renderScopeField("InfraSubinterface", "unit_id");
    const component = await rendered;
    await component.getByRole("button", { name: "No relationship or attribute" }).click();
    await component.getByRole("option", { name: /^Device/ }).click();

    // WHEN
    await component.getByRole("button", { name: "Add a relationship or attribute" }).click();
    await component.getByRole("option", { name: /^VLAN ID/ }).click();

    // THEN
    await expect.element(component.getByText("Device")).toBeVisible();
    await expect.element(component.getByText("VLAN ID")).toBeVisible();
    expect(formRef.current?.getValues("allocation_scope")).toEqual(["device", "vlan_id"]);
  });

  test("removes a chosen field", async () => {
    // GIVEN
    const { formRef, rendered } = renderScopeField("InfraSubinterface", "unit_id", [
      "device",
      "vlan_id",
    ]);
    const component = await rendered;

    // WHEN
    await component.getByRole("button", { name: "Remove Device" }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Remove Device" }))
      .not.toBeInTheDocument();
    expect(formRef.current?.getValues("allocation_scope")).toEqual(["vlan_id"]);
  });

  test("lists the fields of a generic kind", async () => {
    // GIVEN
    const component = await renderScopeField("InfraEndpoint", "port").rendered;

    // WHEN
    await component.getByRole("button", { name: "No relationship or attribute" }).click();

    // THEN
    await expect.element(component.getByRole("option", { name: /^Site/ })).toBeVisible();
  });

  test("warns that numbers cannot repeat across scopes when the attribute is unique on its own", async () => {
    // GIVEN
    const component = await renderScopeField("InfraCircuit", "circuit_number", ["provider"])
      .rendered;

    // WHEN
    const warning = component.getByText(/must be unique across every Circuit/);

    // THEN
    await expect.element(warning).toBeVisible();
  });

  test("shows no warning while no scope is chosen", async () => {
    // GIVEN
    const component = await renderScopeField("InfraCircuit", "circuit_number").rendered;

    // WHEN
    const warning = component.getByText(/must be unique across every Circuit/);

    // THEN
    await expect.element(warning).not.toBeInTheDocument();
  });

  test("explains that the node has no field to scope by when none can be chosen", async () => {
    // GIVEN
    const component = await renderScopeField("BuiltinTag", "weight").rendered;

    // WHEN
    const emptyState = component.getByText(
      "Tag has no required attribute or relationship to scope by."
    );

    // THEN
    await expect.element(emptyState).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "No relationship or attribute" }))
      .toBeDisabled();
  });
});
