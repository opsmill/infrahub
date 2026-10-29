import { beforeEach, describe, expect, test } from "vitest";

import { store } from "@/shared/stores";

import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../../tests/fake/schema";
import {
  type NumberPoolRangeRow,
  NumberPoolRangesInput,
  validateRangeBound,
  validateRangeOrder,
  validateRangeOverlap,
} from "./number-pool-ranges-input";

const row = (start: number | null, end: number | null): NumberPoolRangeRow => ({
  start,
  end,
  allocation_weight: null,
});

const vlanSchema = generateNodeSchema({
  kind: "InfraVLAN",
  attributes: [
    generateAttributeSchema({
      name: "vlan_id",
      kind: "Number",
      parameters: { min_value: 10, max_value: 4094 },
    }),
  ],
});

interface RangesHarnessProps {
  initialRows: Array<NumberPoolRangeRow>;
  // a pool for InfraVLAN.vlan_id, whose numbers run from 10 to 4094; without it the bounds have no limits
  nodeKind?: string;
}

function RangesHarness({ initialRows, nodeKind = "" }: RangesHarnessProps) {
  return (
    <TestForm
      defaultValues={{
        node: { value: nodeKind },
        node_attribute: { value: "vlan_id" },
        ranges: initialRows,
      }}
    >
      <NumberPoolRangesInput />
    </TestForm>
  );
}

describe("NumberPoolRangesInput", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [vlanSchema]);
    store.set(genericSchemasAtom, []);
  });

  test("refuses a start below the minimum the attribute accepts", async () => {
    // GIVEN
    const component = await render(
      <RangesHarness nodeKind="InfraVLAN" initialRows={[row(5, 100)]} />
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("Value must be at least 10")).toBeVisible();
    await expect
      .element(component.getByRole("spinbutton", { name: "Start of range 1" }))
      .toHaveAttribute("aria-invalid", "true");
  });

  test("refuses an end above the maximum the attribute accepts", async () => {
    // GIVEN
    const component = await render(
      <RangesHarness nodeKind="InfraVLAN" initialRows={[row(100, 5000)]} />
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("Value must be at most 4094")).toBeVisible();
    await expect
      .element(component.getByRole("spinbutton", { name: "End of range 1" }))
      .toHaveAttribute("aria-invalid", "true");
  });

  test("accepts a range running exactly from the attribute's minimum to its maximum", async () => {
    // GIVEN
    const component = await render(
      <RangesHarness nodeKind="InfraVLAN" initialRows={[row(10, 4094)]} />
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect
      .element(component.getByRole("spinbutton", { name: "Start of range 1" }))
      .toHaveAttribute("aria-invalid", "false");
    await expect
      .element(component.getByRole("spinbutton", { name: "End of range 1" }))
      .toHaveAttribute("aria-invalid", "false");
  });

  test("explains the order in which ranges are used", async () => {
    // WHEN
    const component = await render(<RangesHarness initialRows={[row(1, 10)]} />);

    // THEN
    await expect
      .element(
        component.getByText(
          "Highest weight is used first. Ranges with equal weight are used from the lowest start."
        )
      )
      .toBeVisible();
    await expect
      .element(component.getByRole("spinbutton", { name: "Weight of range 1" }))
      .toHaveAttribute("placeholder", "0");
  });

  test("shows MIN and MAX in a start and an end left empty", async () => {
    // WHEN
    const component = await render(<RangesHarness initialRows={[row(null, null)]} />);

    // THEN
    await expect
      .element(component.getByRole("spinbutton", { name: "Start of range 1" }))
      .toHaveAttribute("placeholder", "MIN");
    await expect
      .element(component.getByRole("spinbutton", { name: "End of range 1" }))
      .toHaveAttribute("placeholder", "MAX");
  });

  test("accepts a range whose end is cleared", async () => {
    // GIVEN
    const component = await render(<RangesHarness initialRows={[row(100, 199)]} />);

    // WHEN
    await component.getByRole("spinbutton", { name: "End of range 1" }).clear();
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect
      .element(component.getByRole("spinbutton", { name: "End of range 1" }))
      .toHaveAttribute("aria-invalid", "false");
  });

  test("adds an empty row", async () => {
    // GIVEN
    const component = await render(<RangesHarness initialRows={[row(1, 10)]} />);

    // WHEN
    await component.getByRole("button", { name: "Add range" }).click();

    // THEN
    await expect
      .element(component.getByRole("spinbutton", { name: "Start of range 2" }))
      .toHaveValue(null);
  });

  test("keeps rows in the order entered after editing one", async () => {
    // GIVEN
    const component = await render(<RangesHarness initialRows={[row(40, 50), row(1, 19)]} />);

    // WHEN
    await component.getByRole("spinbutton", { name: "End of range 1" }).fill("55");
    await component.getByRole("spinbutton", { name: "Start of range 2" }).click();

    // THEN
    await expect
      .element(component.getByRole("spinbutton", { name: "Start of range 1" }))
      .toHaveValue(40);
    await expect
      .element(component.getByRole("spinbutton", { name: "Start of range 2" }))
      .toHaveValue(1);
  });

  test("tells the user the pool needs a range once every row is removed", async () => {
    // GIVEN
    const component = await render(<RangesHarness initialRows={[row(1, 10)]} />);

    // WHEN
    await component.getByRole("button", { name: "Remove range 1" }).click();

    // THEN
    await expect
      .element(component.getByText("No ranges. The pool can't hand out numbers until you add one."))
      .toBeVisible();
  });

  test("clears the overlap on both rows once one of them is fixed", async () => {
    // GIVEN
    const component = await render(<RangesHarness initialRows={[row(100, 199), row(150, 250)]} />);
    await component.getByRole("button", { name: "Submit" }).click();
    await expect.element(component.getByText("Overlaps 150 – 250")).toBeVisible();

    // WHEN
    await component.getByRole("spinbutton", { name: "Start of range 2" }).fill("200");

    // THEN
    await expect.poll(() => component.getByText(/Overlaps/).query()).toBeNull();
  });

  test("clears the overlap on the remaining row once the other row is removed", async () => {
    // GIVEN
    const component = await render(<RangesHarness initialRows={[row(100, 199), row(150, 250)]} />);
    await component.getByRole("button", { name: "Submit" }).click();
    await expect.element(component.getByText("Overlaps 150 – 250")).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Remove range 2" }).click();

    // THEN
    await expect.poll(() => component.getByText(/Overlaps/).query()).toBeNull();
    await expect
      .element(component.getByRole("spinbutton", { name: "End of range 1" }))
      .toHaveAttribute("aria-invalid", "false");
  });

  test("does not flag an untouched empty row when another row is removed before saving", async () => {
    // GIVEN
    const component = await render(<RangesHarness initialRows={[row(1, 10), row(20, 30)]} />);
    await component.getByRole("button", { name: "Add range" }).click();

    // WHEN
    await component.getByRole("button", { name: "Remove range 1" }).click();

    // THEN
    await expect.poll(() => component.getByText("Required").query()).toBeNull();
  });

  test("flags a row whose end is below its start, without reporting it as an overlap", async () => {
    // GIVEN
    const component = await render(<RangesHarness initialRows={[row(100, 199), row(250, 50)]} />);

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("End is below start")).toBeVisible();
    await expect
      .element(component.getByRole("spinbutton", { name: "End of range 2" }))
      .toHaveAttribute("aria-invalid", "true");
    await expect.poll(() => component.getByText(/Overlaps/).query()).toBeNull();
  });
});

describe("validateRangeBound", () => {
  test("accepts a whole number", () => {
    // WHEN
    const result = validateRangeBound(100);

    // THEN
    expect(result).toBe(true);
  });

  test("allows a range with no start or no end", () => {
    // WHEN
    const result = validateRangeBound(null);

    // THEN
    expect(result).toBe(true);
  });

  test("accepts zero and negative numbers, which an attribute without a minimum holds", () => {
    // WHEN
    const results = [validateRangeBound(0), validateRangeBound(-4)];

    // THEN
    expect(results).toEqual([true, true]);
  });

  test.each([
    [1.5, "Whole number"],
    [9_007_199_254_740_992, "Too large"],
    [-9_007_199_254_740_992, "Too small"],
  ])("refuses %d with %s", (value, message) => {
    // WHEN
    const result = validateRangeBound(value);

    // THEN
    expect(result).toBe(message);
  });
});

describe("validateRangeOverlap", () => {
  test("accepts ranges that do not overlap", () => {
    // WHEN
    const result = validateRangeOverlap([row(100, 199), row(300, 399)], 0);

    // THEN
    expect(result).toBe(true);
  });

  test("names the bounds of every range the row overlaps", () => {
    // GIVEN
    const rows = [row(1, 100), row(5, 10), row(90, 120)];

    // WHEN
    const result = validateRangeOverlap(rows, 0);

    // THEN
    expect(result).toBe("Overlaps 5 – 10, 90 – 120");
  });

  test("treats an empty end as reaching the largest number", () => {
    // WHEN
    const result = validateRangeOverlap([row(100, 199), row(150, null)], 0);

    // THEN
    expect(result).toBe("Overlaps 150 – MAX");
  });

  test("treats an empty start as starting at 1", () => {
    // WHEN
    const result = validateRangeOverlap([row(null, 10), row(1, 5)], 1);

    // THEN
    expect(result).toBe("Overlaps 1 – 10");
  });

  test("allows a range without an end above the other ranges", () => {
    // WHEN
    const result = validateRangeOverlap([row(null, 99), row(100, null)], 0);

    // THEN
    expect(result).toBe(true);
  });

  test("ignores a row whose end is below its start", () => {
    // WHEN
    const result = validateRangeOverlap([row(100, 199), row(250, 50)], 0);

    // THEN
    expect(result).toBe(true);
  });
});

describe("validateRangeOrder", () => {
  test("accepts a range that starts and ends on the same number", () => {
    // WHEN
    const result = validateRangeOrder([row(100, 100)], 0);

    // THEN
    expect(result).toBe(true);
  });

  test("refuses a range whose end is below its start", () => {
    // WHEN
    const result = validateRangeOrder([row(200, 100)], 0);

    // THEN
    expect(result).toBe("End is below start");
  });

  test.each([
    [null, 100],
    [100, null],
    [null, null],
  ])("accepts a range from %s to %s", (start, end) => {
    // WHEN
    const result = validateRangeOrder([row(start, end)], 0);

    // THEN
    expect(result).toBe(true);
  });

  test("refuses a range with an empty start whose end is 0", () => {
    // WHEN
    const result = validateRangeOrder([row(null, 0)], 0);

    // THEN
    expect(result).toBe("End is below start");
  });
});
