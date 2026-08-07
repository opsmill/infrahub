import { format } from "date-fns";
import { afterEach, describe, expect, test } from "vitest";

import { QSP } from "@/shared/config/qsp";

import { METADATA_UPDATED_AT } from "@/entities/nodes/object/domain/model/metadata-filter-definitions";

import { render } from "../../../../../../tests/components/render";
import { DateMetadataFilterForm } from "./date-metadata-filter-form";

interface AppliedFilter {
  name: string;
  value: string;
}

function seedAppliedFilters(filters: AppliedFilter[]) {
  window.history.replaceState(
    null,
    "",
    `/?${QSP.FILTER}=${encodeURIComponent(JSON.stringify(filters))}`
  );
}

function getAppliedFilterValue(filterName: string): string {
  const raw = new URLSearchParams(window.location.search).get(QSP.FILTER);
  if (!raw) throw new Error(`expected the ${QSP.FILTER} query param to be set`);

  const filters: AppliedFilter[] = JSON.parse(raw);
  const filter = filters.find((entry) => entry.name === filterName);
  if (!filter) throw new Error(`expected a ${filterName} filter in ${raw}`);

  return filter.value;
}

// The HH:MM picked in the date picker has to survive into the applied filter value:
// a value truncated to the date portion silently widens the filter by a whole day.
describe("DateMetadataFilterForm", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  test("carries the picked time into a new 'after' filter", async () => {
    // GIVEN
    const dayInCurrentMonth = new Date();
    dayInCurrentMonth.setDate(15);
    const component = await render(<DateMetadataFilterForm definition={METADATA_UPDATED_AT} />);

    // WHEN
    await component
      .getByRole("option", { name: `Choose ${format(dayInCurrentMonth, "PPPP")}`, exact: true })
      .click();
    await component.getByRole("option", { name: "9:35 PM", exact: true }).click();
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    const applied = new Date(getAppliedFilterValue("node_metadata__updated_at__after"));
    expect(applied.getDate()).toBe(15);
    expect(applied.getHours()).toBe(21);
    expect(applied.getMinutes()).toBe(35);
  });

  test("carries the picked time into an existing 'before' filter when only the time changes", async () => {
    // GIVEN
    const midnight = new Date();
    midnight.setHours(0, 0, 0, 0);
    seedAppliedFilters([
      { name: "node_metadata__updated_at__before", value: midnight.toISOString() },
    ]);
    const component = await render(<DateMetadataFilterForm definition={METADATA_UPDATED_AT} />);

    // WHEN
    await component.getByRole("option", { name: "11:59 PM", exact: true }).click();
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    const applied = new Date(getAppliedFilterValue("node_metadata__updated_at__before"));
    expect(applied.getDate()).toBe(midnight.getDate());
    expect(applied.getHours()).toBe(23);
    expect(applied.getMinutes()).toBe(59);
  });
});
