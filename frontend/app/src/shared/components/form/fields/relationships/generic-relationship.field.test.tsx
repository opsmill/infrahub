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
    // GIVEN a generic peer implemented by two concrete nodes
    const component = await render(
      <TestForm>
        <GenericRelationshipField {...defaultProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    // WHEN the user opens the kind picker
    await component.getByRole("combobox", { name: "Kind" }).click();

    // THEN both `used_by` entries are resolved to options — one schema lookup per entry,
    // none of them dropped.
    await expect.element(component.getByRole("option", { name: /Device A/ })).toBeVisible();
    await expect.element(component.getByRole("option", { name: /Device B/ })).toBeVisible();
  });

  test("auto-selects the kind when the generic has a single implementation", async () => {
    // GIVEN a generic implemented by exactly one node
    const soleGeneric = generateGenericSchema({
      kind: "TestSoleGeneric",
      name: "SoleGeneric",
      label: "Sole Generic",
      relationships: [],
      used_by: ["TestDeviceA"],
    });
    store.set(genericSchemasAtom, [soleGeneric]);

    // WHEN the field renders against it
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

    // THEN the only kind is picked for the user, so the node input is immediately usable
    await expect
      .element(component.getByRole("combobox", { name: "Kind" }))
      .toHaveTextContent("Device A");
    await expect.poll(() => component.getByText("Select a kind first").query()).toBeNull();
  });

  // A relationship whose peer is the *generic* BuiltinIPAddress: `getPoolKindFromSchema`
  // sets `field.pool` for it, but until IFC-2764 the pool UI was never rendered on the
  // generic branch, making "allocate from pool" unreachable.
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

    // Same shape, but implemented by a single node: with only one candidate kind there is
    // nothing to override.
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

    // Not fresh object literals, so the extra pool-default field survives assignment to
    // `getRelationships`' NodeCore[] return type without an assertion.
    const addressPoolNode = {
      id: "pool-1",
      display_label: "Loopbacks pool",
      __typename: "CoreIPAddressPool",
      default_address_type: { value: "IpamIPAddress" },
    };

    // A second address pool, so a re-allocation has somewhere else to go: re-picking the pool a
    // value already came from deliberately restores that allocation rather than staging a new one.
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

    // What a pool-backed relationship holds once its allocation has resolved: the allocated
    // address itself, still carrying the pool as its source.
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
        // `getFormFieldFromRelationship` sets this to the peer schema kind, which for a
        // generic peer is the generic itself — no pool's default_address_type equals it.
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
      // GIVEN a from-pool-capable relationship pointing at the generic, with no value yet
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );

      // THEN both tabs are offered and the object one is active, since nothing is allocated
      await expect
        .element(component.getByRole("tab", { name: "Object" }))
        .toHaveAttribute("data-state", "active");
      await expect
        .element(component.getByRole("tab", { name: "From pool" }))
        .toHaveAttribute("data-state", "inactive");
    });

    test("opens on the object tab when the value came from a pool, badged with that pool", async () => {
      // GIVEN an allocation that has already resolved to a concrete address
      const component = await render(
        <TestForm defaultValues={{ primary_address: allocatedValue }}>
          <GenericRelationshipField {...poolProps} defaultValue={allocatedValue} />
        </TestForm>
      );

      // THEN the object tab is the one shown: the pool tab is for staging a *new* allocation and
      // has nothing to show for one that resolved, while the object tab holds the allocated
      // address and the label names the pool it came from.
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

      // AND neither override is offered: a resolved allocation cannot be re-cut.
      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
      await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    });

    test("re-allocates a resolved value from another pool, type override and all", async () => {
      vi.mocked(getRelationships).mockImplementation(async ({ peer }) =>
        peer === "CoreIPAddressPool" ? [addressPoolNode, otherAddressPoolNode] : []
      );

      // GIVEN a field holding an address already allocated from "Loopbacks pool"
      const onSubmit = vi.fn();
      const component = await render(
        <TestForm defaultValues={{ primary_address: allocatedValue }} onSubmit={onSubmit}>
          <GenericRelationshipField {...poolProps} defaultValue={allocatedValue} />
        </TestForm>
      );
      await expect.element(component.getByText("10.0.0.1/24")).toBeVisible();

      // WHEN the user goes to the pool tab and allocates from a different pool
      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Management pool" }).click();

      // THEN a fresh allocation is staged, with the type override back in reach — this is the
      // path that replaces opening on the pool tab.
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
      // GIVEN the field on its object tab, where no kind is chosen yet
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await expect.element(component.getByText("Select a kind first")).toBeVisible();

      // WHEN the user switches to the pool tab without touching the kind picker
      await component.getByRole("tab", { name: "From pool" }).click();

      // THEN the pool is selectable straight away: the kind gate belongs to the object
      // picker, and a pool allocation has no use for it.
      await expect
        .element(component.getByTestId("select-open-pool-option-button"))
        .toBeInTheDocument();
      await expect.poll(() => component.getByText("Select a kind first").query()).toBeNull();
    });

    test("keeps the kind picker on the object tab and out of the pool tab", async () => {
      // GIVEN the field on its object tab
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await expect.element(component.getByRole("combobox", { name: "Kind" })).toBeVisible();

      // WHEN the user switches to the pool tab
      await component.getByRole("tab", { name: "From pool" }).click();

      // THEN the kind picker is gone: it filters the object list, and the pool's own default
      // kind is what an allocation targets — "Type to allocate" overrides that instead.
      await expect.poll(() => component.getByRole("combobox", { name: "Kind" }).query()).toBeNull();
      await expect.element(component.getByRole("combobox", { name: "Pool" })).toBeVisible();
    });

    test("filters the pool list by the generic's implementations, not by a single default kind", async () => {
      // GIVEN the field's pool tab
      const component = await render(
        <TestForm>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );
      await component.getByRole("tab", { name: "From pool" }).click();

      // WHEN the user opens the pool list
      await component.getByTestId("select-open-pool-option-button").click();

      // THEN the pool query is filtered over the whole `used_by` set, which the tab reads from
      // the peer generic rather than from the object tab. Pinning the singular
      // `default_address_type__value` to the generic matches no pool at all, and pinning it to
      // a selected kind would defeat allocating a B from an A-defaulted pool.
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
      // GIVEN a form whose submitted data we capture
      const onSubmit = vi.fn();
      const component = await render(
        <TestForm onSubmit={onSubmit}>
          <GenericRelationshipField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
        </TestForm>
      );

      // WHEN the user allocates from a pool and submits, without ever picking a kind
      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Loopbacks pool" }).click();
      await component.getByRole("button", { name: "Submit" }).click();

      // THEN no allocated kind is sent: the pool's own default kind rides on the source, where
      // the override field reads it as its placeholder. Same payload as before the tabs.
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
      // GIVEN a pool-capable field and a node reachable under one of the generic's kinds
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

      // WHEN the user picks a kind and a node on the object tab, then submits
      await component.getByRole("combobox", { name: "Kind" }).click();
      await component.getByRole("option", { name: /Ipam IP Address/ }).click();
      await component.getByRole("combobox", { name: "Ipam IP Address" }).click();
      await component.getByRole("option", { name: "10.0.0.1/24" }).click();
      await component.getByRole("button", { name: "Submit" }).click();

      // THEN a plain user-sourced node is sent, untouched by the pool tab
      await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
      expect(onSubmit.mock.calls[0]?.[0]?.primary_address).toEqual({
        source: { type: "user" },
        value: { id: "addr-1", display_label: "10.0.0.1/24", __typename: "IpamIPAddress" },
      });
    });

    test("clears the staged value when the user switches tabs", async () => {
      // GIVEN an allocation staged on the pool tab
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

      // WHEN the user goes to the object tab and back
      await component.getByRole("tab", { name: "Object" }).click();
      await component.getByRole("tab", { name: "From pool" }).click();

      // THEN the allocation is gone: a value cannot be both picked and allocated, and this is
      // what stops the nested from-pool fields (prefix length, allocated kind) leaking across.
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

      // THEN nothing to override before an allocation exists
      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();

      // WHEN the user allocates from a pool
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Loopbacks pool" }).click();

      // THEN the override appears, empty, hinting the pool default it would otherwise use
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

      // A bare combobox reads as a required choice; the label and its help text are what say
      // the pool already has a default and that touching this replaces it. The tooltip mounts
      // its text only while hovered, so assert it that way rather than via a description.
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

      // WHEN the user overrides the target kind with a sibling implementation
      await component.getByTestId("pool-kind-select").click();
      await component.getByRole("option", { name: /Test IP Address/ }).click();
      await component.getByRole("button", { name: "Submit" }).click();

      // THEN it rides in the value, which is what the mutation sends
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
      // GIVEN a generic peer with exactly one candidate kind
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

      // WHEN the user allocates from a pool
      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "Loopbacks pool" }).click();

      // THEN the prefix-length override still shows, but a one-option kind dropdown does not
      await expect.element(component.getByTestId("pool-prefix-length-input")).toBeVisible();
      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
    });

    test("hides the kind override when the value is a resolved node", async () => {
      // GIVEN a field whose pool allocation already resolved to a concrete address
      const component = await render(
        <TestForm defaultValues={{ primary_address: allocatedValue }}>
          <GenericRelationshipField {...poolProps} defaultValue={allocatedValue} />
        </TestForm>
      );
      await expect.element(component.getByText("10.0.0.1/24")).toBeVisible();

      // WHEN the user goes looking for the override on the pool tab
      await component.getByRole("tab", { name: "From pool" }).click();

      // THEN the pool selector is reachable, but there is nothing left to re-target: the
      // address exists, so its kind can no longer change. Only a fresh allocation, staged from
      // this tab, can name another kind.
      await expect
        .element(component.getByTestId("select-open-pool-option-button"))
        .toBeInTheDocument();
      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
      await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    });

    test("hides the kind override for a number pool", async () => {
      // GIVEN the same generic peer wired to a number pool, where a target kind is meaningless
      const component = await render(
        <TestForm>
          <GenericRelationshipField
            {...poolProps}
            pool={{ kind: "CoreNumberPool", defaultAllocatedObjectKind: "BuiltinIPAddress" }}
            defaultValue={DEFAULT_FORM_FIELD_VALUE}
          />
        </TestForm>
      );

      // WHEN the user allocates from the number pool
      await component.getByRole("tab", { name: "From pool" }).click();
      await component.getByTestId("select-open-pool-option-button").click();
      await component.getByRole("option", { name: "VLAN ids pool" }).click();

      // THEN neither IP-only override is offered
      await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
      await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    });

    test("disables both tabs when the field is disabled", async () => {
      // GIVEN a disabled field (a read-only or inherited value)
      const component = await render(
        <TestForm>
          <GenericRelationshipField
            {...poolProps}
            disabled
            defaultValue={DEFAULT_FORM_FIELD_VALUE}
          />
        </TestForm>
      );

      // THEN neither mode can be entered — before the tabs, a disabled field kept a live
      // pool button.
      await expect.element(component.getByRole("tab", { name: "Object" })).toBeDisabled();
      await expect.element(component.getByRole("tab", { name: "From pool" })).toBeDisabled();
    });
  });
});
