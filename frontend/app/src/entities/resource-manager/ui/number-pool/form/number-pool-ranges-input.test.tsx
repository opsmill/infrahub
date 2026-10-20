import { describe, expect, test } from "vitest";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import {
  type NumberPoolRangeRow,
  NumberPoolRangesInput,
  validateRangeBound,
  validateRangeOrder,
  validateRangeOverlap,
  validateRangeWeight,
} from "./number-pool-ranges-input";

const row = (start: number, end: number): NumberPoolRangeRow => ({
  start,
  end,
  allocation_weight: null,
});

function RangesHarness({ initialRows }: { initialRows: Array<NumberPoolRangeRow> }) {
  return (
    <TestForm defaultValues={{ ranges: initialRows }}>
      <NumberPoolRangesInput />
    </TestForm>
  );
}

describe("NumberPoolRangesInput", () => {
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

  test.each([
    [Number.NaN, "Required"],
    [1.5, "Whole number"],
    [-4, "Whole number"],
    [9_007_199_254_740_992, "Too large"],
  ])("refuses %d with %s", (value, message) => {
    // WHEN
    const result = validateRangeBound(value);

    // THEN
    expect(result).toBe(message);
  });
});

describe("validateRangeWeight", () => {
  test("accepts an empty weight, which means the range has none", () => {
    // WHEN
    const result = validateRangeWeight(null);

    // THEN
    expect(result).toBe(true);
  });

  test("refuses a weight that is not a whole number", () => {
    // WHEN
    const result = validateRangeWeight(1.5);

    // THEN
    expect(result).toBe("Whole number");
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

  test("ignores rows that are not complete yet", () => {
    // WHEN
    const result = validateRangeOverlap([row(100, 199), row(150, Number.NaN)], 0);

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
});
