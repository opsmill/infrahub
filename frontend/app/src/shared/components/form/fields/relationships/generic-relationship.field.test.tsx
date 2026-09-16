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

  test("offers every implementation of the generic as a kind option", async () => {
    const component = await render(
      <TestForm>
        <GenericRelationshipField {...defaultProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await component.getByRole("combobox", { name: "Kind" }).click();

    await expect.element(component.getByRole("option", { name: /Device A/ })).toBeVisible();
    await expect.element(component.getByRole("option", { name: /Device B/ })).toBeVisible();
  });

  test("auto-selects the kind when the generic has a single implementation", async () => {
    const soleGeneric = generateGenericSchema({
      kind: "TestSoleGeneric",
      name: "SoleGeneric",
      label: "Sole Generic",
      relationships: [],
      used_by: ["TestDeviceA"],
    });
    store.set(genericSchemasAtom, [soleGeneric]);

    const component = await render(
      <TestForm>
        <GenericRelationshipField
          {...defaultProps}
          peer="TestSoleGeneric"
          relationship={generateRelationshipSchema({
            name: "device",
            peer: "TestSoleGeneric",
            kind: "Parent",
            cardinality: "one",
          })}
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
        />
      </TestForm>
    );

    await expect
      .element(component.getByRole("combobox", { name: "Kind" }))
      .toHaveTextContent("Device A");
    await expect.poll(() => component.getByText("Select a kind first").query()).toBeNull();
  });

  // Peer is the *generic* BuiltinIPAddress, which is what makes the pool UI reachable.
  describe("allocate from pool on a generic IP peer", () => {
    const ipGeneric = generateGenericSchema({
      kind: "BuiltinIPAddress",
      name: "IPAddress",
      label: "IP Address",
      relationships: [],
      used_by: ["IpamIPAddress", "TestIPAddress"],
    });

    const ipamAddress = generateNodeSchema({
      kind: "IpamIPAddress",
      name: "IPAddress",
      label: "Ipam IP Address",
      inherit_from: ["BuiltinIPAddress"],
    });

    const testAddress = generateNodeSchema({
      kind: "TestIPAddress",
      name: "TestIPAddress",
      label: "Test IP Address",
      inherit_from: ["BuiltinIPAddress"],
    });

    const soleIpGeneric = generateGenericSchema({
      kind: "SoleIPAddress",
      name: "SoleIPAddress",
      label: "Sole IP Address",
      relationships: [],
      used_by: ["IpamIPAddress"],
    });

    const addressPoolSchema = generateNodeSchema({
      kind: "CoreIPAddressPool",
      name: "IPAddressPool",
      label: "IP Address Pool",
    });

    const numberPoolSchema = generateNodeSchema({
      kind: "CoreNumberPool",
      name: "NumberPool",
      label: "Number Pool",
    });

    // Not fresh object literals: excess-property checking would reject the extra pool default.
    const addressPoolNode = {
      id: "pool-1",
      display_label: "Loopbacks pool",
      __typename: "CoreIPAddressPool",
      default_address_type: { value: "IpamIPAddress" },
    };

    // A second address pool, since re-picking the original pool restores its allocation instead of staging one.
    const otherAddressPoolNode = {
      id: "pool-2",
      display_label: "Management pool",
      __typename: "CoreIPAddressPool",
      default_address_type: { value: "IpamIPAddress" },
    };

    const numberPoolNode = {
      id: "number-pool-1",
      display_label: "VLAN ids pool",
      __typename: "CoreNumberPool",
    };

    // A resolved allocation: the address itself, still sourced from the pool.
    const allocatedValue = {
      source: {
        type: "pool" as const,
        id: "pool-1",
        kind: "CoreIPAddressPool" as const,
        label: "Loopbacks pool",
      },
      value: { id: "addr-1", display_label: "10.0.0.1/24", __typename: "IpamIPAddress" },
    };

    const ipRelationshipSchema = generateRelationshipSchema({
      name: "primary_address",
      peer: "BuiltinIPAddress",
      kind: "Attribute",
      cardinality: "one",
    });

    const poolProps: DynamicRelationshipFieldProps = {
      type: "relationship",
      name: "primary_address",
      label: "Primary address",
      peer: "BuiltinIPAddress",
      relationship: ipRelationshipSchema,
      pool: {
        kind: "CoreIPAddressPool",
        // A generic peer's schema kind is the generic itself, which no pool default equals.
        defaultAllocatedObjectKind: "BuiltinIPAddress",
      },
    };

    beforeEach(() => {
      store.set(nodeSchemasAtom, [ipamAddress, testAddress, addressPoolSchema, numberPoolSchema]);
      store.set(genericSchemasAtom, [ipGeneric, soleIpGeneric]);
      vi.mocked(getRelationships).mockImplementation(async ({ peer }) => {
        if (peer === "CoreIPAddressPool") return [addressPoolNode];
        if (peer === "CoreNumberPool") return [numberPoolNode];
        return [];
      });
    });

    test("presents the two ways of satisfying the field as tabs, starting on Object", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
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
          <GenericRelationshipField {...poolProps} defaultValue={allocatedValue} />
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

      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
      await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    });

    test("re-allocates a resolved value from another pool, type override and all", async () => {
      vi.mocked(getRelationships).mockImplementation(async ({ peer }) =>
        peer === "CoreIPAddressPool" ? [addressPoolNode, otherAddressPoolNode] : []
      );

      const onSubmit = vi.fn();
      const component = await render(
        <TestForm defaultValues={{ primary_address: allocatedValue }} onSubmit={onSubmit}>
          <GenericRelationshipField {...poolProps} defaultValue={allocatedValue} />
        </TestForm>
      );
      await expect.element(component.getByText("10.0.0.1/24")).toBeVisible();

      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Management pool" }).click();

      await expect
        .element(component.getByTestId("select-value"))
        .toHaveTextContent("Management pool");
      await expect.element(component.getByTestId("pool-kind-select")).toBeVisible();

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

    test("offers the pool without making the user choose a kind first", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await expect.element(component.getByText("Select a kind first")).toBeVisible();

      await component.getByRole("tab", { name: "From pool" }).click();

      await expect
        .element(component.getByTestId("select-open-pool-option-button"))
        .toBeInTheDocument();
      await expect.poll(() => component.getByText("Select a kind first").query()).toBeNull();
    });

    test("keeps the kind picker on the object tab and out of the pool tab", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await expect.element(component.getByRole("combobox", { name: "Kind" })).toBeVisible();

      await component.getByRole("tab", { name: "From pool" }).click();

      await expect.poll(() => component.getByRole("combobox", { name: "Kind" }).query()).toBeNull();
      await expect.element(component.getByRole("combobox", { name: "Pool" })).toBeVisible();
    });

    test("filters the pool list by the generic's implementations, not by a single default kind", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await component.getByRole("tab", { name: "From pool" }).click();

      await component.getByTestId("select-open-pool-option-button").click();

      // Filtering by a single kind would hide the pools that default to a sibling kind.
      await expect
        .poll(
          () =>
            vi
              .mocked(getRelationships)
              .mock.calls.map(([params]) => params)
              .find((params) => params.peer === "CoreIPAddressPool")?.filterQuery
        )
        .toEqual({ default_address_type__values: ["IpamIPAddress", "TestIPAddress"] });
    });

    test("leaves the allocation on the pool's own kind until the override is used", async () => {
      const onSubmit = vi.fn();
      const component = await render(
        <TestForm onSubmit={onSubmit}>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
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
      vi.mocked(getRelationships).mockImplementation(async ({ peer }) => {
        if (peer === "CoreIPAddressPool") return [addressPoolNode];
        if (peer === "IpamIPAddress") {
          return [{ id: "addr-1", display_label: "10.0.0.1/24", __typename: "IpamIPAddress" }];
        }
        return [];
      });

      const component = await render(
        <TestForm onSubmit={onSubmit}>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );

      await component.getByRole("combobox", { name: "Kind" }).click();
      await component.getByRole("option", { name: /Ipam IP Address/ }).click();
      await component.getByRole("combobox", { name: "Ipam IP Address" }).click();
      await component.getByRole("option", { name: "10.0.0.1/24" }).click();
      await component.getByRole("button", { name: "Submit" }).click();

      await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
      expect(onSubmit.mock.calls[0]?.[0]?.primary_address).toEqual({
        source: { type: "user" },
        value: { id: "addr-1", display_label: "10.0.0.1/24", __typename: "IpamIPAddress" },
      });
    });

    test("clears the staged value when the user switches tabs", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Loopbacks pool" }).click();
      await expect
        .element(component.getByTestId("select-value"))
        .toHaveTextContent("Loopbacks pool");

      await component.getByRole("tab", { name: "Object" }).click();
      await component.getByRole("tab", { name: "From pool" }).click();

      await expect.poll(() => component.getByTestId("select-value").query()).toBeNull();
      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
    });

    test("offers the kind override below the pool, defaulted to the pool's own kind", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await component.getByRole("tab", { name: "From pool" }).click();

      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();

      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Loopbacks pool" }).click();

      await expect.element(component.getByTestId("pool-kind-select")).toBeVisible();
      await expect
        .element(component.getByTestId("pool-kind-select"))
        .toHaveTextContent("Ipam IP Address");
    });

    test("labels the override and explains that it replaces the pool's default kind", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Loopbacks pool" }).click();

      // The tooltip mounts its text only while hovered, so assert it that way.
      await expect.element(component.getByText("Type to allocate")).toBeVisible();
      await component.getByRole("button", { name: "?" }).last().hover();
      await expect
        .element(component.getByText(/allocates a "Ipam IP Address" by default/))
        .toBeVisible();
    });

    test("writes the picked override into the submitted from-pool value", async () => {
      const onSubmit = vi.fn();
      const component = await render(
        <TestForm onSubmit={onSubmit}>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Loopbacks pool" }).click();

      await component.getByTestId("pool-kind-select").click();
      await component.getByRole("option", { name: /Test IP Address/ }).click();
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
        value: { from_pool: { id: "pool-1", allocatedKind: "TestIPAddress" } },
      });
    });

    test("hides the kind override when the generic has a single implementation", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField
            {...poolProps}
            peer="SoleIPAddress"
            relationship={generateRelationshipSchema({
              name: "primary_address",
              peer: "SoleIPAddress",
              kind: "Attribute",
              cardinality: "one",
            })}
            pool={{ kind: "CoreIPAddressPool", defaultAllocatedObjectKind: "SoleIPAddress" }}
            defaultValue={DEFAULT_FORM_FIELD_VALUE}
          />
        </TestForm>
      );

      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Loopbacks pool" }).click();

      await expect.element(component.getByTestId("pool-prefix-length-input")).toBeVisible();
      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
    });

    test("hides the kind override when the value is a resolved node", async () => {
      const component = await render(
        <TestForm defaultValues={{ primary_address: allocatedValue }}>
          <GenericRelationshipField {...poolProps} defaultValue={allocatedValue} />
        </TestForm>
      );
      await expect.element(component.getByText("10.0.0.1/24")).toBeVisible();

      await component.getByRole("tab", { name: "From pool" }).click();

      await expect
        .element(component.getByTestId("select-open-pool-option-button"))
        .toBeInTheDocument();
      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
      await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    });

    test("hides the kind override for a number pool", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField
            {...poolProps}
            pool={{ kind: "CoreNumberPool", defaultAllocatedObjectKind: "BuiltinIPAddress" }}
            defaultValue={DEFAULT_FORM_FIELD_VALUE}
          />
        </TestForm>
      );

      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "VLAN ids pool" }).click();

      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
      await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    });

    test("disables both tabs when the field is disabled", async () => {
      const component = await render(
        <TestForm>
          <GenericRelationshipField
            {...poolProps}
            disabled
            defaultValue={DEFAULT_FORM_FIELD_VALUE}
          />
        </TestForm>
      );

      await expect.element(component.getByRole("tab", { name: "Object" })).toBeDisabled();
      await expect.element(component.getByRole("tab", { name: "From pool" })).toBeDisabled();
    });
  });
});
