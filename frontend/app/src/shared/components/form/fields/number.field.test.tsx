import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { NumberFieldProps } from "@/shared/components/form/fields/number.field";
import NumberField from "@/shared/components/form/fields/number.field";
import type { FormAttributeValue } from "@/shared/components/form/type";
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

  // A second pool, since re-picking the original pool restores its allocation instead of staging one.
  const otherNumberPoolNode = {
    id: "number-pool-2",
    display_label: "Loopback ids pool",
    __typename: "CoreNumberPool",
  };

  // The edit form's default when a pool records the node's number.
  const trackedValue: FormAttributeValue = {
    source: {
      type: "pool",
      id: "number-pool-1",
      kind: "CoreNumberPool",
      label: "VLAN ids pool",
    },
    value: { from_pool: { id: "number-pool-1", number: 42 } },
  };

  // A number pool is narrowed per node kind and attribute, so its candidates arrive pre-fetched rather than queried.
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

    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("offers a number input only once a pool is picked", async () => {
    const component = await render(
      <TestForm>
        <NumberField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await expect.element(component.getByTestId("select-open-pool-option-button")).toBeVisible();
    await expect.poll(() => component.getByTestId("pool-number-input").query()).toBeNull();

    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "VLAN ids pool" }).click();

    await expect.element(component.getByRole("spinbutton", { name: "Number" })).toBeVisible();
    await expect.element(component.getByTestId("pool-number-input")).toHaveValue(null);
  });

  test("stores the number typed in the pool tab alongside the picked pool", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm onSubmit={onSubmit}>
        <NumberField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "VLAN ids pool" }).click();
    await component.getByRole("spinbutton", { name: "Number" }).fill("42");
    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.vlan_id).toEqual({
      source: {
        type: "pool",
        id: "number-pool-1",
        kind: "CoreNumberPool",
        label: "VLAN ids pool",
      },
      value: { from_pool: { id: "number-pool-1", number: 42 } },
    });
  });

  test("offers no number input for a pool that comes from a template", async () => {
    const component = await render(
      <TestForm>
        <NumberField
          {...poolProps}
          pool={{
            kind: "CoreNumberPool",
            defaultAllocatedObjectKind: "TestDevice",
            options: [numberPoolNode],
            fromPoolRelationshipName: "vlan_id_from_resource_pool",
          }}
        />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "VLAN ids pool" }).click();

    await expect.element(component.getByTestId("select-value")).toHaveTextContent("VLAN ids pool");
    await expect.poll(() => component.getByTestId("pool-number-input").query()).toBeNull();
  });

  test("opens a number recorded in a pool on the From pool tab, showing the pool and the number", async () => {
    const component = await render(
      <TestForm defaultValues={{ vlan_id: trackedValue }}>
        <NumberField {...poolProps} defaultValue={trackedValue} />
      </TestForm>
    );

    await expect
      .element(component.getByRole("tab", { name: "From pool" }))
      .toHaveAttribute("data-state", "active");
    await expect
      .element(component.getByRole("tab", { name: "Value" }))
      .toHaveAttribute("data-state", "inactive");
    await expect.element(component.getByTestId("select-value")).toHaveTextContent("VLAN ids pool");
    await expect.element(component.getByRole("spinbutton", { name: "Number" })).toHaveValue(42);
    await expect
      .element(component.getByTestId("source-pool-badge"))
      .toHaveTextContent("VLAN ids pool");

    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("opens a number the user set on the Value tab", async () => {
    const userValue: FormAttributeValue = { source: { type: "user" }, value: 12 };
    const component = await render(
      <TestForm defaultValues={{ vlan_id: userValue }}>
        <NumberField {...poolProps} defaultValue={userValue} />
      </TestForm>
    );

    await expect
      .element(component.getByRole("tab", { name: "Value" }))
      .toHaveAttribute("data-state", "active");
    await expect.element(component.getByRole("spinbutton")).toHaveValue(12);
  });

  test("shows the number recorded in the pool as the Value tab placeholder", async () => {
    const component = await render(
      <TestForm defaultValues={{ vlan_id: trackedValue }}>
        <NumberField {...poolProps} defaultValue={trackedValue} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "Value" }).click();

    const input = component.getByRole("spinbutton");
    await expect.element(input).toHaveValue(null);
    await expect.element(input).toHaveAttribute("placeholder", "42");
  });

  test("submits the default unchanged after visiting the Value tab and returning", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm defaultValues={{ vlan_id: trackedValue }} onSubmit={onSubmit}>
        <NumberField {...poolProps} defaultValue={trackedValue} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "Value" }).click();
    await component.getByRole("tab", { name: "From pool" }).click();

    await expect.element(component.getByTestId("select-value")).toHaveTextContent("VLAN ids pool");
    await expect.element(component.getByRole("spinbutton", { name: "Number" })).toHaveValue(42);

    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.vlan_id).toEqual(trackedValue);
  });

  test("moves the number to another pool, keeping it", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm defaultValues={{ vlan_id: trackedValue }} onSubmit={onSubmit}>
        <NumberField
          {...poolProps}
          pool={{
            kind: "CoreNumberPool",
            defaultAllocatedObjectKind: "TestDevice",
            options: [numberPoolNode, otherNumberPoolNode],
          }}
          defaultValue={trackedValue}
        />
      </TestForm>
    );
    await expect.element(component.getByRole("spinbutton", { name: "Number" })).toHaveValue(42);

    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Loopback ids pool" }).click();

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
      value: { from_pool: { id: "number-pool-2", number: 42 } },
    });
  });

  test("keeps the default intact when a number is typed after re-picking the original pool", async () => {
    const onSubmit = vi.fn();
    const defaultValue = structuredClone(trackedValue);
    const component = await render(
      <TestForm defaultValues={{ vlan_id: structuredClone(trackedValue) }} onSubmit={onSubmit}>
        <NumberField
          {...poolProps}
          pool={{
            kind: "CoreNumberPool",
            defaultAllocatedObjectKind: "TestDevice",
            options: [numberPoolNode, otherNumberPoolNode],
          }}
          defaultValue={defaultValue}
        />
      </TestForm>
    );

    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Loopback ids pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "VLAN ids pool" }).click();
    await component.getByRole("spinbutton", { name: "Number" }).fill("7");
    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.vlan_id).toEqual({
      source: trackedValue.source,
      value: { from_pool: { id: "number-pool-1", number: 7 } },
    });
    expect(defaultValue).toEqual(trackedValue);
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

    // A number pool source carries no prefix length and no target kind.
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

  test("disables both tabs when the field is disabled", async () => {
    const component = await render(
      <TestForm>
        <NumberField {...poolProps} disabled />
      </TestForm>
    );

    await expect.element(component.getByRole("tab", { name: "Value" })).toBeDisabled();
    await expect.element(component.getByRole("tab", { name: "From pool" })).toBeDisabled();
  });
});
