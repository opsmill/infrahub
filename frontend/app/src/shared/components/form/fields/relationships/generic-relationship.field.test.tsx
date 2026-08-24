import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { DynamicRelationshipFieldProps } from "@/shared/components/form/type";
import { store } from "@/shared/stores";

import { getRelationships } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { GenericRelationshipField } from "./generic-relationship.field";

vi.mock("@/entities/nodes/relationships/domain/use-cases/get-relationships");

describe("GenericRelationshipField", () => {
  // A generic peer implemented by TWO concrete nodes, so the field cannot
  // auto-select a single kind.
  const genericPeer = generateGenericSchema({
    kind: "TestGenericDevice",
    name: "GenericDevice",
    label: "Generic Device",
    relationships: [],
    used_by: ["TestDeviceA", "TestDeviceB"],
  });

  const deviceA = generateNodeSchema({
    kind: "TestDeviceA",
    name: "DeviceA",
    label: "Device A",
    inherit_from: ["TestGenericDevice"],
  });

  const deviceB = generateNodeSchema({
    kind: "TestDeviceB",
    name: "DeviceB",
    label: "Device B",
    inherit_from: ["TestGenericDevice"],
  });

  const relationshipSchema = generateRelationshipSchema({
    name: "device",
    peer: "TestGenericDevice",
    kind: "Parent",
    cardinality: "one",
  });

  beforeEach(() => {
    store.set(nodeSchemasAtom, [deviceA, deviceB]);
    store.set(genericSchemasAtom, [genericPeer]);
    vi.mocked(getRelationships).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const defaultProps: DynamicRelationshipFieldProps = {
    type: "relationship",
    name: "device",
    label: "Device",
    peer: "TestGenericDevice",
    relationship: relationshipSchema,
  };

  test("pre-selects the related node from the default value when the generic has several implementations", async () => {
    // GIVEN a parent value already resolved to the concrete node "atl1-edge"
    const defaultValue = {
      source: { type: "user" as const },
      value: { id: "device-a-1", display_label: "atl1-edge", __typename: "TestDeviceA" },
    };

    // WHEN the field renders with that value wired into the form
    const component = await render(
      <TestForm defaultValues={{ device: defaultValue }}>
        <GenericRelationshipField {...defaultProps} defaultValue={defaultValue} />
      </TestForm>
    );

    // THEN the relationship node itself is displayed as selected (the node picker only
    // renders once the kind is derived), not left on the "Select a kind first" placeholder.
    await expect.element(component.getByText("atl1-edge")).toBeVisible();
    await expect.poll(() => component.getByText("Select a kind first").query()).toBeNull();
  });

  test("keeps the kind cleared after the user explicitly clears it", async () => {
    // GIVEN a field pre-selected from a default value
    const defaultValue = {
      source: { type: "user" as const },
      value: { id: "device-a-1", display_label: "atl1-edge", __typename: "TestDeviceA" },
    };
    const component = await render(
      <TestForm defaultValues={{ device: defaultValue }}>
        <GenericRelationshipField {...defaultProps} defaultValue={defaultValue} />
      </TestForm>
    );
    await expect.element(component.getByText("atl1-edge")).toBeVisible();

    // WHEN the user opens the kind picker and deselects the current kind
    await component.getByRole("combobox", { name: "Kind" }).click();
    await component.getByRole("option", { name: /Device A/ }).click();

    // THEN it stays cleared instead of snapping back to the default-derived kind.
    await expect.element(component.getByText("Select a kind first")).toBeVisible();
  });

  test("clears the selected node when the kind is changed", async () => {
    // GIVEN a field pre-selected to "atl1-edge" under kind "Device A"
    const defaultValue = {
      source: { type: "user" as const },
      value: { id: "device-a-1", display_label: "atl1-edge", __typename: "TestDeviceA" },
    };
    const component = await render(
      <TestForm defaultValues={{ device: defaultValue }}>
        <GenericRelationshipField {...defaultProps} defaultValue={defaultValue} />
      </TestForm>
    );
    await expect.element(component.getByText("atl1-edge")).toBeVisible();

    // WHEN the user switches to a different kind
    await component.getByRole("combobox", { name: "Kind" }).click();
    await component.getByRole("option", { name: /Device B/ }).click();

    // THEN the node picked under the previous kind is cleared (no longer valid).
    await expect.poll(() => component.getByText("atl1-edge").query()).toBeNull();
  });

  test("shows the kind placeholder when no default value is provided", async () => {
    // GIVEN no pre-selected value
    // WHEN the field renders
    const component = await render(
      <TestForm>
        <GenericRelationshipField {...defaultProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    // THEN the user must pick a kind first (no auto-selection with several implementations)
    await expect.element(component.getByText("Select a kind first")).toBeVisible();
  });
});
