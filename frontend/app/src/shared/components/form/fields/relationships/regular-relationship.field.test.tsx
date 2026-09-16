import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { DynamicRelationshipFieldProps } from "@/shared/components/form/type";
import { store } from "@/shared/stores";

import { getRelationships } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import {
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { NodeRelationshipField } from "./regular-relationship.field";

vi.mock("@/entities/nodes/relationships/domain/use-cases/get-relationships");

describe("NodeRelationshipField", () => {
  // A concrete IP peer pins the allocated kind, so a pool is offered but no type override.
  const ipamAddress = generateNodeSchema({
    kind: "IpamIPAddress",
    name: "IPAddress",
    label: "Ipam IP Address",
    relationships: [],
  });

  const addressPoolSchema = generateNodeSchema({
    kind: "CoreIPAddressPool",
    name: "IPAddressPool",
    label: "IP Address Pool",
    relationships: [],
  });

  // Not a fresh object literal: excess-property checking would reject the extra pool default.
  const addressPoolNode = {
    id: "pool-1",
    display_label: "Loopbacks pool",
    __typename: "CoreIPAddressPool",
    default_address_type: { value: "IpamIPAddress" },
  };

  // A second pool, since re-picking the original pool restores its allocation instead of staging one.
  const otherAddressPoolNode = {
    id: "pool-2",
    display_label: "Management pool",
    __typename: "CoreIPAddressPool",
    default_address_type: { value: "IpamIPAddress" },
  };

  const addressNode = {
    id: "addr-1",
    display_label: "10.0.0.1/24",
    __typename: "IpamIPAddress",
  };

  // A resolved allocation: the node itself, still sourced from the pool.
  const allocatedValue = {
    source: {
      type: "pool" as const,
      id: "pool-1",
      kind: "CoreIPAddressPool" as const,
      label: "Loopbacks pool",
    },
    value: addressNode,
  };

  const relationshipSchema = generateRelationshipSchema({
    name: "primary_address",
    peer: "IpamIPAddress",
    kind: "Attribute",
    cardinality: "one",
  });

  const poolProps: DynamicRelationshipFieldProps = {
    type: "relationship",
    name: "primary_address",
    label: "Primary address",
    peer: "IpamIPAddress",
    relationship: relationshipSchema,
    pool: {
      kind: "CoreIPAddressPool",
      defaultAllocatedObjectKind: "IpamIPAddress",
    },
  };

  beforeEach(() => {
    store.set(nodeSchemasAtom, [ipamAddress, addressPoolSchema]);
    vi.mocked(getRelationships).mockImplementation(async ({ peer }) => {
      if (peer === "CoreIPAddressPool") return [addressPoolNode];
      if (peer === "IpamIPAddress") return [addressNode];
      return [];
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders without a tab strip when no pool can satisfy the field", async () => {
    const component = await render(
      <TestForm>
        <NodeRelationshipField
          {...poolProps}
          pool={undefined}
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
        />
      </TestForm>
    );

    await expect.element(component.getByText("Primary address")).toBeVisible();
    await expect.poll(() => component.getByRole("tab", { name: "Object" }).query()).toBeNull();
    await expect.poll(() => component.getByRole("tab", { name: "From pool" }).query()).toBeNull();
  });

  test("presents the two ways of satisfying the field as tabs, starting on Object", async () => {
    const component = await render(
      <TestForm>
        <NodeRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await expect
      .element(component.getByRole("tab", { name: "Object" }))
      .toHaveAttribute("data-state", "active");
    await expect
      .element(component.getByRole("tab", { name: "From pool" }))
      .toHaveAttribute("data-state", "inactive");
  });

  test("opens on the object tab when the value came from a pool, badged with that pool", async () => {
    const component = await render(
      <TestForm defaultValues={{ primary_address: allocatedValue }}>
        <NodeRelationshipField {...poolProps} defaultValue={allocatedValue} />
      </TestForm>
    );

    await expect
      .element(component.getByRole("tab", { name: "Object" }))
      .toHaveAttribute("data-state", "active");
    await expect
      .element(component.getByRole("tab", { name: "From pool" }))
      .toHaveAttribute("data-state", "inactive");
    await expect.element(component.getByText("10.0.0.1/24")).toBeVisible();
    await expect
      .element(component.getByTestId("source-pool-badge"))
      .toHaveTextContent("Loopbacks pool");

    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("re-allocates an already-allocated value from another pool", async () => {
    vi.mocked(getRelationships).mockImplementation(async ({ peer }) => {
      if (peer === "CoreIPAddressPool") return [addressPoolNode, otherAddressPoolNode];
      if (peer === "IpamIPAddress") return [addressNode];
      return [];
    });

    const onSubmit = vi.fn();
    const component = await render(
      <TestForm defaultValues={{ primary_address: allocatedValue }} onSubmit={onSubmit}>
        <NodeRelationshipField {...poolProps} defaultValue={allocatedValue} />
      </TestForm>
    );
    await expect.element(component.getByText("10.0.0.1/24")).toBeVisible();

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Management pool" }).click();

    await expect
      .element(component.getByTestId("select-value"))
      .toHaveTextContent("Management pool");
    await expect.element(component.getByTestId("pool-prefix-length-input")).toBeVisible();

    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.primary_address).toEqual({
      source: {
        type: "pool",
        id: "pool-2",
        kind: "CoreIPAddressPool",
        label: "Management pool",
        defaultPrefixLength: null,
        defaultAllocatedKind: "IpamIPAddress",
      },
      value: { from_pool: { id: "pool-2" } },
    });
  });

  test("offers no type override, because a concrete peer pins the kind", async () => {
    const component = await render(
      <TestForm>
        <NodeRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Loopbacks pool" }).click();

    await expect.element(component.getByTestId("pool-prefix-length-input")).toBeVisible();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("offers no overrides on an object template, which cannot carry them", async () => {
    const component = await render(
      <TestForm>
        <NodeRelationshipField
          {...poolProps}
          pool={{
            kind: "CoreIPAddressPool",
            defaultAllocatedObjectKind: "IpamIPAddress",
            fromPoolRelationshipName: "primary_address_from_resource_pool",
          }}
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
        />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Loopbacks pool" }).click();

    // A template submits through `<name>_from_resource_pool`, whose input carries neither override.
    await expect.element(component.getByTestId("select-value")).toHaveTextContent("Loopbacks pool");
    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("submits the same from-pool payload the pool button produced", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm onSubmit={onSubmit}>
        <NodeRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Loopbacks pool" }).click();
    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.primary_address).toEqual({
      source: {
        type: "pool",
        id: "pool-1",
        kind: "CoreIPAddressPool",
        label: "Loopbacks pool",
        defaultPrefixLength: null,
        defaultAllocatedKind: "IpamIPAddress",
      },
      value: { from_pool: { id: "pool-1" } },
    });
  });

  test("submits the node picked on the object tab", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm onSubmit={onSubmit}>
        <NodeRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await component.getByRole("combobox", { name: "Primary address" }).click();
    await component.getByRole("option", { name: "10.0.0.1/24" }).click();
    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.primary_address).toEqual({
      source: { type: "user" },
      value: addressNode,
    });
  });

  test("clears the staged value when the user switches tabs", async () => {
    const component = await render(
      <TestForm>
        <NodeRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Loopbacks pool" }).click();
    await expect.element(component.getByTestId("select-value")).toHaveTextContent("Loopbacks pool");

    await component.getByRole("tab", { name: "Object" }).click();
    await component.getByRole("tab", { name: "From pool" }).click();

    await expect.poll(() => component.getByTestId("select-value").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
  });

  test("disables both tabs when the field is disabled", async () => {
    const component = await render(
      <TestForm>
        <NodeRelationshipField {...poolProps} disabled defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await expect.element(component.getByRole("tab", { name: "Object" })).toBeDisabled();
    await expect.element(component.getByRole("tab", { name: "From pool" })).toBeDisabled();
  });

  test("disables the pool control itself on a disabled field", async () => {
    const component = await render(
      <TestForm>
        <NodeRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    // A disabled tab cannot be pressed, so open the panel before disabling the field.
    await component.getByRole("tab", { name: "From pool" }).click();
    await component.rerender(
      <TestForm>
        <NodeRelationshipField {...poolProps} disabled defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    // The panel stays mounted while the strip is locked, so its controls must refuse on their own.
    await expect.element(component.getByTestId("select-open-pool-option-button")).toBeDisabled();
  });
});
