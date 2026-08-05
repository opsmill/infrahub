import { format } from "date-fns";
import { afterEach, describe, expect, test } from "vitest";

import { QSP } from "@/shared/config/qsp";

import { METADATA_UPDATED_AT } from "@/entities/nodes/object/domain/metadata-filter-definitions";

import { render } from "../../../../../../tests/components/render";
import { DateMetadataFilterForm } from "./date-metadata-filter-form";

// The HH:MM selected in the date picker must be carried into the applied filter
// value, not silently truncated to the date portion.

function getFilterValue(filterName: string): string {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get(QSP.FILTER);
  expect(raw, `expected ${QSP.FILTER} query param to be set`).toBeTruthy();
  const filters: Array<{ name: string; value: unknown }> = JSON.parse(raw as string);
  const filter = filters.find((f) => f.name === filterName);
  expect(filter, `expected filter ${filterName} in ${raw}`).toBeDefined();
  return filter?.value as string;
}

function seedFilters(filters: Array<{ name: string; value: string }>) {
  window.history.replaceState(
    null,
    "",
    `/?${QSP.FILTER}=${encodeURIComponent(JSON.stringify(filters))}`
  );
}

describe("DateMetadataFilterForm", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  test("keeps the selected time in the applied 'after' filter", async () => {
    // GIVEN
    const component = await render(<DateMetadataFilterForm definition={METADATA_UPDATED_AT} />);
    const dayInCurrentMonth = new Date();
    dayInCurrentMonth.setDate(15);

    // WHEN
    await component.getByLabelText(`Choose ${format(dayInCurrentMonth, "PPPP")}`).click();
    await component.getByText("9:35 PM", { exact: true }).click();
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    const value = getFilterValue("node_metadata__updated_at__after");
    const applied = new Date(value);
    expect(applied.getHours()).toBe(21);
    expect(applied.getMinutes()).toBe(35);
    expect(applied.getDate()).toBe(15);
  });

  test("changing only the time of an existing 'before' filter updates the applied value", async () => {
    // GIVEN an applied "before <today> 00:00" filter, as in the issue's reproduction steps
    const midnight = new Date();
    midnight.setHours(0, 0, 0, 0);
    seedFilters([{ name: "node_metadata__updated_at__before", value: midnight.toISOString() }]);
    const component = await render(<DateMetadataFilterForm definition={METADATA_UPDATED_AT} />);

    // WHEN only the time is changed to 23:59
    await component.getByText("11:59 PM", { exact: true }).click();
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    const value = getFilterValue("node_metadata__updated_at__before");
    const applied = new Date(value);
    expect(applied.getHours()).toBe(23);
    expect(applied.getMinutes()).toBe(59);
    expect(applied.getDate()).toBe(midnight.getDate());
  });
});
