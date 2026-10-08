import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import type { RangeRow } from "@/entities/resource-manager/domain/model/number-pool-range";
import { RangesField } from "@/entities/resource-manager/ui/number-pool-form/ranges-field";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";

const renderRanges = (
  ranges: RangeRow[],
  {
    onSubmit = vi.fn(),
    limits,
  }: { onSubmit?: () => void; limits?: Parameters<typeof RangesField>[0]["limits"] } = {}
) =>
  render(
    <TestForm defaultValues={{ ranges }} onSubmit={onSubmit}>
      <RangesField limits={limits} />
    </TestForm>
  );

describe("RangesField", () => {
  test("lists each range with labelled Start, End and Weight inputs", async () => {
    // GIVEN
    const ranges = [
      { rangeId: "r1", start: "100", end: "199", weight: "10" },
      { start: "300", end: "399", weight: "" },
    ];

    // WHEN
    const component = await renderRanges(ranges);

    // THEN
    await expect
      .element(component.getByRole("textbox", { name: "Start" }).nth(1))
      .toHaveValue("300");
    await expect.element(component.getByRole("textbox", { name: "End" }).nth(0)).toHaveValue("199");
    await expect
      .element(component.getByRole("textbox", { name: "Weight" }).nth(0))
      .toHaveValue("10");
  });

  test("appends an empty row at the end when adding a range", async () => {
    // GIVEN
    const component = await renderRanges([{ start: "100", end: "199", weight: "" }]);

    // WHEN
    await component.getByRole("button", { name: "Add range" }).click();

    // THEN
    await expect
      .element(component.getByRole("textbox", { name: "Start" }).nth(0))
      .toHaveValue("100");
    await expect.element(component.getByRole("textbox", { name: "Start" }).nth(1)).toHaveValue("");
  });

  test("removes the row whose remove button is pressed", async () => {
    // GIVEN
    const component = await renderRanges([
      { start: "100", end: "199", weight: "" },
      { start: "300", end: "399", weight: "" },
    ]);

    // WHEN
    await component.getByRole("button", { name: "Remove range" }).nth(0).click();

    // THEN
    expect(component.getByRole("textbox", { name: "Start" }).elements()).toHaveLength(1);
    await expect.element(component.getByRole("textbox", { name: "Start" })).toHaveValue("300");
  });

  test("shows that the pool cannot hand out numbers when it has no range", async () => {
    // GIVEN
    const ranges: RangeRow[] = [];

    // WHEN
    const component = await renderRanges(ranges);

    // THEN
    await expect
      .element(component.getByText("No ranges. The pool can't hand out numbers until you add one."))
      .toBeVisible();
  });

  test("submits with no range", async () => {
    // GIVEN
    const onSubmit = vi.fn();
    const component = await renderRanges([], { onSubmit });

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.poll(() => onSubmit).toHaveBeenCalledWith({ ranges: [] });
  });

  test("shows an error on the row after leaving an end lower than its start", async () => {
    // GIVEN
    const component = await renderRanges([{ start: "200", end: "", weight: "" }]);
    await component.getByRole("textbox", { name: "End" }).fill("100");

    // WHEN
    await userEvent.tab();

    // THEN
    await expect.element(component.getByText("Must not be lower than start")).toBeVisible();
  });

  test("does not show an error on a field the user has not left yet", async () => {
    // GIVEN
    const component = await renderRanges([{ start: "", end: "", weight: "" }]);
    await component.getByRole("textbox", { name: "Start" }).fill("abc");

    // WHEN
    await component.getByRole("textbox", { name: "Start" }).fill("abcd");

    // THEN
    await expect.element(component.getByText("Whole number")).not.toBeInTheDocument();
  });

  test("names the other range on both overlapping rows and blocks the submit", async () => {
    // GIVEN
    const onSubmit = vi.fn();
    const component = await renderRanges(
      [
        { start: "100", end: "199", weight: "" },
        { start: "150", end: "250", weight: "" },
      ],
      { onSubmit }
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("Overlaps 150 – 250")).toBeVisible();
    await expect.element(component.getByText("Overlaps 100 – 199")).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test("clears the overlap on the other row once the overlap is fixed", async () => {
    // GIVEN
    const component = await renderRanges([
      { start: "100", end: "199", weight: "" },
      { start: "150", end: "250", weight: "" },
    ]);
    await component.getByRole("button", { name: "Submit" }).click();
    await expect.element(component.getByText("Overlaps 150 – 250")).toBeVisible();

    // WHEN
    await component.getByRole("textbox", { name: "Start" }).nth(1).fill("200");

    // THEN
    await expect.element(component.getByText("Overlaps 150 – 250")).not.toBeInTheDocument();
  });

  test("blocks the submit when a weight is negative", async () => {
    // GIVEN
    const onSubmit = vi.fn();
    const component = await renderRanges([{ start: "1", end: "10", weight: "-1" }], { onSubmit });

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("Whole number of 0 or more")).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test("shows the clipped bounds of a range that goes past the attribute limits and still submits", async () => {
    // GIVEN
    const onSubmit = vi.fn();
    const component = await renderRanges([{ start: "0", end: "5000", weight: "" }], {
      onSubmit,
      limits: { attribute: "vlan_id", min: 1, max: 4094 },
    });

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect
      .element(component.getByText("Clipped to 1 – 4,094 by the vlan_id limits"))
      .toBeVisible();
    await expect.poll(() => onSubmit).toHaveBeenCalled();
  });

  test("keeps the rows in place while a weight is typed", async () => {
    // GIVEN
    const component = await renderRanges([
      { start: "100", end: "199", weight: "1" },
      { start: "300", end: "399", weight: "" },
    ]);

    // WHEN
    await component.getByRole("textbox", { name: "Weight" }).nth(1).fill("100");

    // THEN
    await expect
      .element(component.getByRole("textbox", { name: "Start" }).nth(0))
      .toHaveValue("100");
  });

  test("submits the rows as typed, keeping the stored range id", async () => {
    // GIVEN
    const onSubmit = vi.fn();
    const component = await renderRanges(
      [{ rangeId: "range-1", start: "100", end: "199", weight: "" }],
      { onSubmit }
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect
      .poll(() => onSubmit)
      .toHaveBeenCalledWith({
        ranges: [{ rangeId: "range-1", start: "100", end: "199", weight: "" }],
      });
  });
});
