import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { NumberFieldProps } from "@/shared/components/form/fields/number.field";
import NumberField from "@/shared/components/form/fields/number.field";
import type { AttributeValueFromPool, FormAttributeValue } from "@/shared/components/form/type";
import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";

describe("NumberField", () => {
  const numberPoolSchema = generateNodeSchema({
    kind: "CoreNumberPool",
    name: "NumberPool",
    label: "Number Pool",
    relationships: [],
  });

  const numberPoolNode = {
    id: "number-pool-1",
    display_label: "VLAN ids pool",
    __typename: "CoreNumberPool",
  };

  // A second pool, so a re-allocation has somewhere else to go: re-picking the pool a value
  // already came from deliberately restores that allocation rather than staging a new one.
  const otherNumberPoolNode = {
    id: "number-pool-2",
    display_label: "Loopback ids pool",
    __typename: "CoreNumberPool",
  };

  // What a pool-backed field holds once its allocation has resolved: the number itself, still
  // carrying the pool as its source. `AttributeValueFromPool["value"]` only spells out the
  // *pending* marker, so this casts exactly as `getDefaultValueFromPool` does for real data.
  const allocatedValue: FormAttributeValue = {
    source: {
      type: "pool",
      id: "number-pool-1",
      kind: "CoreNumberPool",
      label: "VLAN ids pool",
    },
    value: 42 as unknown as AttributeValueFromPool["value"],
  };

  // A number pool is configured for one node kind and one attribute, so the candidates are
  // pre-fetched and handed over on `pool.options` rather than queried — the one place the
  // converged channel still differs from an IP pool.
  const poolProps: NumberFieldProps = {
    name: "vlan_id",
    label: "VLAN id",
    pool: {
      kind: "CoreNumberPool",
      defaultAllocatedObjectKind: "TestDevice",
      options: [numberPoolNode],
    },
  };

  beforeEach(() => {
    store.set(nodeSchemasAtom, [numberPoolSchema]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders without a tab strip when no pool serves this attribute", async () => {
    const component = await render(
      <TestForm>
        <NumberField {...poolProps} pool={undefined} />
      </TestForm>
    );

    await expect.element(component.getByRole("spinbutton")).toBeVisible();
    await expect.poll(() => component.getByRole("tab", { name: "Value" }).query()).toBeNull();
    await expect.poll(() => component.getByRole("tab", { name: "From pool" }).query()).toBeNull();
  });

  test("presents the two ways of filling the field in as tabs, starting on Value", async () => {
    const component = await render(
      <TestForm>
        <NumberField {...poolProps} />
      </TestForm>
    );

    await expect
      .element(component.getByRole("tab", { name: "Value" }))
      .toHaveAttribute("data-state", "active");
    await expect
      .element(component.getByRole("tab", { name: "From pool" }))
      .toHaveAttribute("data-state", "inactive");
    await expect.element(component.getByRole("spinbutton")).toBeVisible();
  });

  test("reaches the pre-fetched pools from the pool tab", async () => {
    const component = await render(
      <TestForm>
        <NumberField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "VLAN ids pool" }).click();

    await expect.element(component.getByTestId("select-value")).toHaveTextContent("VLAN ids pool");
  });

  test("offers neither override for a number pool", async () => {
    const component = await render(
      <TestForm>
        <NumberField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "VLAN ids pool" }).click();

    // A number pool has no mask, and what it allocates is a number rather than an object with
    // a kind, so both overrides withhold themselves and the panel is the pool alone.
    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("opens on the value tab when the value came from a pool, badged with that pool", async () => {
    const component = await render(
      <TestForm defaultValues={{ vlan_id: allocatedValue }}>
        <NumberField {...poolProps} defaultValue={allocatedValue} />
      </TestForm>
    );

    // The pool tab is for staging a *new* allocation; it has nothing to show for one that has
    // already resolved. The value tab holds the allocated number, and the label says where it
    // came from — strictly more than the pool tab could offer.
    await expect
      .element(component.getByRole("tab", { name: "Value" }))
      .toHaveAttribute("data-state", "active");
    await expect
      .element(component.getByRole("tab", { name: "From pool" }))
      .toHaveAttribute("data-state", "inactive");
    await expect.element(component.getByRole("spinbutton")).toHaveValue(42);
    await expect
      .element(component.getByTestId("source-pool-badge"))
      .toHaveTextContent("VLAN ids pool");

    // And neither override is offered: a resolved allocation cannot be re-cut.
    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("re-allocates an already-allocated number from another pool", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm defaultValues={{ vlan_id: allocatedValue }} onSubmit={onSubmit}>
        <NumberField
          {...poolProps}
          pool={{
            kind: "CoreNumberPool",
            defaultAllocatedObjectKind: "TestDevice",
            options: [numberPoolNode, otherNumberPoolNode],
          }}
          defaultValue={allocatedValue}
        />
      </TestForm>
    );
    await expect.element(component.getByRole("spinbutton")).toHaveValue(42);

    // WHEN the user goes to the pool tab and allocates from a different pool
    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Loopback ids pool" }).click();

    // THEN a fresh allocation is staged — this is the path that replaces opening on the
    // pool tab.
    await expect
      .element(component.getByTestId("select-value"))
      .toHaveTextContent("Loopback ids pool");

    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.vlan_id).toEqual({
      source: {
        type: "pool",
        id: "number-pool-2",
        kind: "CoreNumberPool",
        label: "Loopback ids pool",
      },
      value: { from_pool: { id: "number-pool-2" } },
    });
  });

  test("submits the same from-pool payload the pool button produced", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm onSubmit={onSubmit}>
        <NumberField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "VLAN ids pool" }).click();
    await component.getByRole("button", { name: "Submit" }).click();

    // A number pool source carries no defaults: `makePoolSource` drops the prefix length and
    // target kind for it, exactly as the old number-pool button did.
    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.vlan_id).toEqual({
      source: {
        type: "pool",
        id: "number-pool-1",
        kind: "CoreNumberPool",
        label: "VLAN ids pool",
      },
      value: { from_pool: { id: "number-pool-1" } },
    });
  });

  test("submits the typed number untouched by the pool tab", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm onSubmit={onSubmit}>
        <NumberField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("spinbutton").fill("42");
    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.vlan_id).toEqual({
      source: { type: "user" },
      value: 42,
    });
  });

  test("clears the staged value when the user switches tabs", async () => {
    const component = await render(
      <TestForm>
        <NumberField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "VLAN ids pool" }).click();
    await expect.element(component.getByTestId("select-value")).toHaveTextContent("VLAN ids pool");

    await component.getByRole("tab", { name: "Value" }).click();
    await expect.element(component.getByRole("spinbutton")).toHaveValue(null);

    await component.getByRole("tab", { name: "From pool" }).click();
    await expect.poll(() => component.getByTestId("select-value").query()).toBeNull();
  });

  test("disables both tabs and the pool control when the field is disabled", async () => {
    const component = await render(
      <TestForm>
        <NumberField {...poolProps} disabled />
      </TestForm>
    );

    // Before the tabs, a disabled number field kept a live pool button.
    await expect.element(component.getByRole("tab", { name: "Value" })).toBeDisabled();
    await expect.element(component.getByRole("tab", { name: "From pool" })).toBeDisabled();
  });
});
