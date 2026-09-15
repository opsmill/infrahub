import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { InputFieldProps } from "@/shared/components/form/fields/input.field";
import InputField from "@/shared/components/form/fields/input.field";
import type { AttributeValueFromPool, FormAttributeValue } from "@/shared/components/form/type";
import { store } from "@/shared/stores";

import { getRelationships } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/entities/nodes/relationships/domain/use-cases/get-relationships");

describe("InputField", () => {
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

  // What a pool-backed field holds once its allocation has resolved: the prefix itself, still
  // carrying the pool as its source. `AttributeValueFromPool["value"]` only spells out the
  // *pending* marker, so this casts exactly as `getDefaultValueFromPool` does for real data.
  const allocatedValue: FormAttributeValue = {
    source: {
      type: "pool",
      id: "pool-1",
      kind: "CoreIPPrefixPool",
      label: "Site prefixes pool",
    },
    value: "10.0.0.0/16" as unknown as AttributeValueFromPool["value"],
  };

  // The `prefix` attribute of an IP prefix node: pool-capable while creating the object.
  const poolProps: InputFieldProps = {
    name: "prefix",
    label: "Prefix",
    pool: {
      kind: "CoreIPPrefixPool",
      defaultAllocatedObjectKind: "IpamIPPrefix",
    },
  };

  beforeEach(() => {
    store.set(nodeSchemasAtom, [prefixPoolSchema]);
    vi.mocked(getRelationships).mockImplementation(async ({ peer }) =>
      peer === "CoreIPPrefixPool" ? [prefixPoolNode] : []
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders without a tab strip when no pool can satisfy the field", async () => {
    const component = await render(
      <TestForm>
        <InputField {...poolProps} pool={undefined} />
      </TestForm>
    );

    await expect.element(component.getByRole("textbox")).toBeVisible();
    await expect.poll(() => component.getByRole("tab", { name: "Value" }).query()).toBeNull();
    await expect.poll(() => component.getByRole("tab", { name: "From pool" }).query()).toBeNull();
  });

  test("presents the two ways of filling the field in as tabs, starting on Value", async () => {
    const component = await render(
      <TestForm>
        <InputField {...poolProps} />
      </TestForm>
    );

    await expect
      .element(component.getByRole("tab", { name: "Value" }))
      .toHaveAttribute("data-state", "active");
    await expect
      .element(component.getByRole("tab", { name: "From pool" }))
      .toHaveAttribute("data-state", "inactive");
    await expect.element(component.getByRole("textbox")).toBeVisible();
  });

  test("shows the typed value on the value tab and no pool marker button", async () => {
    const component = await render(
      <TestForm>
        <InputField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("textbox").fill("10.0.0.0/16");

    // The value tab is always an editable input now: the "Allocated by pool" button that used
    // to stand in its place, needing a click before anything could be typed, is gone.
    await expect.element(component.getByRole("textbox")).toHaveValue("10.0.0.0/16");
    await expect.poll(() => component.getByText("Allocated by pool").query()).toBeNull();
  });

  test("opens on the value tab when the value came from a pool, badged with that pool", async () => {
    const component = await render(
      <TestForm defaultValues={{ prefix: allocatedValue }}>
        <InputField {...poolProps} defaultValue={allocatedValue} />
      </TestForm>
    );

    // The pool tab is for staging a *new* allocation; it has nothing to show for one that has
    // already resolved. The value tab holds the allocated prefix, and the label says where it
    // came from — strictly more than the pool tab could offer.
    await expect
      .element(component.getByRole("tab", { name: "Value" }))
      .toHaveAttribute("data-state", "active");
    await expect
      .element(component.getByRole("tab", { name: "From pool" }))
      .toHaveAttribute("data-state", "inactive");
    await expect.element(component.getByRole("textbox")).toHaveValue("10.0.0.0/16");
    await expect
      .element(component.getByTestId("source-pool-badge"))
      .toHaveTextContent("Site prefixes pool");

    // And neither override is offered: a resolved allocation cannot be re-cut.
    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("re-allocates an already-allocated value from another pool", async () => {
    vi.mocked(getRelationships).mockImplementation(async ({ peer }) =>
      peer === "CoreIPPrefixPool" ? [prefixPoolNode, otherPrefixPoolNode] : []
    );

    const onSubmit = vi.fn();
    const component = await render(
      <TestForm defaultValues={{ prefix: allocatedValue }} onSubmit={onSubmit}>
        <InputField {...poolProps} defaultValue={allocatedValue} />
      </TestForm>
    );
    await expect.element(component.getByRole("textbox")).toHaveValue("10.0.0.0/16");

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
    expect(onSubmit.mock.calls[0]?.[0]?.prefix).toEqual({
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

  test("offers the prefix-length override but no type override", async () => {
    const component = await render(
      <TestForm>
        <InputField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Site prefixes pool" }).click();

    // The attribute belongs to the node being created, so its kind is already settled.
    await expect.element(component.getByTestId("pool-prefix-length-input")).toBeVisible();
    await expect.poll(() => component.getByTestId("pool-kind-select").query()).toBeNull();
  });

  test("submits the same from-pool payload the pool button produced", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm onSubmit={onSubmit}>
        <InputField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Site prefixes pool" }).click();
    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.prefix).toEqual({
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

  test("submits the typed value untouched by the pool tab", async () => {
    const onSubmit = vi.fn();
    const component = await render(
      <TestForm onSubmit={onSubmit}>
        <InputField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("textbox").fill("10.0.0.0/16");
    await component.getByRole("button", { name: "Submit" }).click();

    await expect.poll(() => onSubmit.mock.calls.length).toBeGreaterThan(0);
    expect(onSubmit.mock.calls[0]?.[0]?.prefix).toEqual({
      source: { type: "user" },
      value: "10.0.0.0/16",
    });
  });

  test("clears the staged value when the user switches tabs", async () => {
    const component = await render(
      <TestForm>
        <InputField {...poolProps} />
      </TestForm>
    );

    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Site prefixes pool" }).click();
    await expect
      .element(component.getByTestId("select-value"))
      .toHaveTextContent("Site prefixes pool");

    await component.getByRole("tab", { name: "Value" }).click();

    // The typed value starts empty rather than inheriting the allocation…
    await expect.element(component.getByRole("textbox")).toHaveValue("");

    await component.getByRole("tab", { name: "From pool" }).click();

    // …and the allocation is gone on the way back, along with its nested override fields.
    await expect.poll(() => component.getByTestId("select-value").query()).toBeNull();
    await expect.poll(() => component.getByTestId("pool-prefix-length-input").query()).toBeNull();
  });

  test("disables both tabs and the pool control when the field is disabled", async () => {
    const component = await render(
      <TestForm>
        <InputField {...poolProps} />
      </TestForm>
    );

    // No field opens on the pool tab, and a disabled tab cannot be pressed, so open the panel
    // first and let the field be disabled underneath it.
    await component.getByRole("tab", { name: "From pool" }).click();
    await component.rerender(
      <TestForm>
        <InputField {...poolProps} disabled />
      </TestForm>
    );

    // Before the tabs, a disabled field kept a live pool button.
    await expect.element(component.getByRole("tab", { name: "Value" })).toBeDisabled();
    await expect.element(component.getByRole("tab", { name: "From pool" })).toBeDisabled();
    await expect.element(component.getByTestId("select-open-pool-option-button")).toBeDisabled();
  });

  test("disables the prefix-length override on a disabled field", async () => {
    const component = await render(
      <TestForm>
        <InputField {...poolProps} />
      </TestForm>
    );

    // The override only exists for a pending allocation, so stage one before the field is
    // disabled — afterwards the strip is locked and the panel unreachable.
    await component.getByRole("tab", { name: "From pool" }).click();
    await component.getByTestId("select-open-pool-option-button").click();
    await component.getByRole("option", { name: "Site prefixes pool" }).click();
    await expect.element(component.getByTestId("pool-prefix-length-input")).toBeVisible();

    await component.rerender(
      <TestForm>
        <InputField {...poolProps} disabled />
      </TestForm>
    );

    await expect.element(component.getByTestId("pool-prefix-length-input")).toBeDisabled();
  });
});
