import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { store } from "@/shared/stores";

import { getRelationships } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import {
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import RelationshipHierarchicalField from "./relationship-hierarchical.field";

vi.mock("@/entities/nodes/relationships/domain/use-cases/get-relationships");

describe("RelationshipHierarchicalField", () => {
  const ipamPrefix = generateNodeSchema({
    kind: "IpamIPPrefix",
    name: "IPPrefix",
    label: "Ipam IP Prefix",
    relationships: [],
  });

  const prefixPoolSchema = generateNodeSchema({
    kind: "CoreIPPrefixPool",
    name: "IPPrefixPool",
    label: "IP Prefix Pool",
    relationships: [],
  });

  // Not a fresh object literal, so the extra pool-default field survives assignment to
  // `getRelationships`' NodeCore[] return type without an assertion.
  const prefixPoolNode = {
    id: "pool-1",
    display_label: "Site prefixes pool",
    __typename: "CoreIPPrefixPool",
    default_prefix_type: { value: "IpamIPPrefix" },
  };

  // A second pool, so a re-allocation has somewhere else to go: re-picking the pool a value
  // already came from deliberately restores that allocation rather than staging a new one.
  const otherPrefixPoolNode = {
    id: "pool-2",
    display_label: "Datacentre prefixes pool",
    __typename: "CoreIPPrefixPool",
    default_prefix_type: { value: "IpamIPPrefix" },
  };

  const prefixNode = {
    id: "prefix-1",
    display_label: "10.0.0.0/16",
    __typename: "IpamIPPrefix",
  };

  // What a pool-backed relationship holds once its allocation has resolved: the allocated node
  // itself, still carrying the pool as its source.
  const allocatedValue = {
    source: {
      type: "pool" as const,
      id: "pool-1",
      kind: "CoreIPPrefixPool" as const,
      label: "Site prefixes pool",
    },
    value: prefixNode,
  };

  const oneRelationship = generateRelationshipSchema({
    name: "ip_prefix",
    peer: "IpamIPPrefix",
    kind: "Attribute",
    cardinality: "one",
    hierarchical: "IpamIPPrefix",
  });

  const poolProps = {
    name: "ip_prefix",
    label: "IP Prefix",
    relationship: oneRelationship,
    pool: {
      kind: "CoreIPPrefixPool",
      defaultAllocatedObjectKind: "IpamIPPrefix",
    },
  };

  beforeEach(() => {
    store.set(nodeSchemasAtom, [ipamPrefix, prefixPoolSchema]);
    vi.mocked(getRelationships).mockImplementation(async ({ peer }) => {
      if (peer === "CoreIPPrefixPool") return [prefixPoolNode];
      if (peer === "IpamIPPrefix") return [prefixNode];
      return [];
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders without a tab strip when no pool can satisfy the field", async () => {
    const component = await render(
      <TestForm>
        <RelationshipHierarchicalField
          {...poolProps}
          pool={undefined}
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
        />
      </TestForm>
    );

    await expect.element(component.getByText("IP Prefix")).toBeVisible();
    await expect.poll(() => component.getByRole("tab", { name: "Object" }).query()).toBeNull();
    await expect.poll(() => component.getByRole("tab", { name: "From pool" }).query()).toBeNull();
  });

  test("renders a cardinality-many relationship untabbed, since no pool applies to it", async () => {
    const component = await render(
      <TestForm>
        <RelationshipHierarchicalField
          {...poolProps}
          relationship={generateRelationshipSchema({
            name: "ip_prefixes",
            peer: "IpamIPPrefix",
            kind: "Attribute",
            cardinality: "many",
            hierarchical: "IpamIPPrefix",
          })}
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
        />
      </TestForm>
    );

    // A pool only ever satisfies a field holding one value, so the strip must not appear even
    // though the schema handed this field a pool.
    await expect.element(component.getByText("IP Prefix")).toBeVisible();
    await expect.poll(() => component.getByRole("tab", { name: "From pool" }).query()).toBeNull();
  });

  test("presents the two ways of satisfying the field as tabs, starting on Object", async () => {
    const component = await render(
      <TestForm>
        <RelationshipHierarchicalField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
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
      <TestForm defaultValues={{ ip_prefix: allocatedValue }}>
        <RelationshipHierarchicalField {...poolProps} defaultValue={allocatedValue} />
      </TestForm>
    );

    // The pool tab is for staging a *new* allocation; it has nothing to show for one that has
    // already resolved. The object tab holds the allocated prefix, and the label names the pool
    // it came from — where the field used to feed the picker a synthetic node labelled
    // "Allocated by pool", which said neither.
    await expect
      .element(component.getByRole("tab", { name: "Object" }))
      .toHaveAttribute("data-state", "active");
    await expect
      .element(component.getByRole("tab", { name: "From pool" }))
      .toHaveAttribute("data-state", "inactive");
    await expect.element(component.getByText("10.0.0.0/16")).toBeVisible();
    await expect
      .element(component.getByTestId("source-pool-badge"))
      .toHaveTextContent("Site prefixes pool");
    await expect.poll(() => component.getByText("Allocated by pool").query()).toBeNull();

    // And neither override is offered: a resolved allocation cannot be re-cut.
    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("re-allocates an already-allocated value from another pool", async () => {
    vi.mocked(getRelationships).mockImplementation(async ({ peer }) => {
      if (peer === "CoreIPPrefixPool") return [prefixPoolNode, otherPrefixPoolNode];
      if (peer === "IpamIPPrefix") return [prefixNode];
      return [];
    });

    const onSubmit = vi.fn();
    const component = await render(
      <TestForm defaultValues={{ ip_prefix: allocatedValue }} onSubmit={onSubmit}>
        <RelationshipHierarchicalField {...poolProps} defaultValue={allocatedValue} />
      </TestForm>
    );
    await expect.element(component.getByText("10.0.0.0/16")).toBeVisible();

    // WHEN the user goes to the pool tab and allocates from a different pool
    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Datacentre prefixes pool" }).click();

    // THEN a fresh allocation is staged, mask override and all — this is the path that
    // replaces opening on the pool tab.
    await expect
      .element(component.getByTestId("select-value"))
      .toHaveTextContent("Datacentre prefixes pool");
    await expect.element(component.getByTestId("pool-prefix-length-input")).toBeVisible();

    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.ip_prefix).toEqual({
      source: {
        type: "pool",
        id: "pool-2",
        kind: "CoreIPPrefixPool",
        label: "Datacentre prefixes pool",
        defaultPrefixLength: null,
        defaultAllocatedKind: "IpamIPPrefix",
      },
      value: { from_pool: { id: "pool-2" } },
    });
  });

  test("offers no type override, because a concrete peer pins the kind", async () => {
    const component = await render(
      <TestForm>
        <RelationshipHierarchicalField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Site prefixes pool" }).click();

    await expect.element(component.getByTestId("pool-prefix-length-input")).toBeVisible();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("submits the same from-pool payload the pool button produced", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm onSubmit={onSubmit}>
        <RelationshipHierarchicalField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Site prefixes pool" }).click();
    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.ip_prefix).toEqual({
      source: {
        type: "pool",
        id: "pool-1",
        kind: "CoreIPPrefixPool",
        label: "Site prefixes pool",
        defaultPrefixLength: null,
        defaultAllocatedKind: "IpamIPPrefix",
      },
      value: { from_pool: { id: "pool-1" } },
    });
  });

  test("clears the staged value when the user switches tabs", async () => {
    const component = await render(
      <TestForm>
        <RelationshipHierarchicalField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Site prefixes pool" }).click();
    await expect
      .element(component.getByTestId("select-value"))
      .toHaveTextContent("Site prefixes pool");

    await component.getByRole("tab", { name: "Object" }).click();
    await component.getByRole("tab", { name: "From pool" }).click();

    await expect.poll(() => component.getByTestId("select-value").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
  });

  test("disables both tabs and the pool control when the field is disabled", async () => {
    const component = await render(
      <TestForm>
        <RelationshipHierarchicalField {...poolProps} defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    // No field opens on the pool tab, and a disabled tab cannot be pressed, so open the panel
    // first and let the field be disabled underneath it.
    await component.getByRole("tab", { name: "From pool" }).click();
    await component.rerender(
      <TestForm>
        <RelationshipHierarchicalField
          {...poolProps}
          disabled
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
        />
      </TestForm>
    );

    // The field never forwarded `disabled` at all before, so a read-only field kept a live
    // pool button beside a live picker.
    await expect.element(component.getByRole("tab", { name: "Object" })).toBeDisabled();
    await expect.element(component.getByRole("tab", { name: "From pool" })).toBeDisabled();
    await expect.element(component.getByTestId("select-open-pool-option-button")).toBeDisabled();
  });
});
