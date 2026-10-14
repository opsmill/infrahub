import { describe, expect, it } from "vitest";

import { COLUMN_MAX_WIDTH } from "@/shared/components/table/style";

import { getGridTemplateColumns } from "@/entities/branches/ui/branches-table/get-grid-template-columns";

describe("getGridTemplateColumns", () => {
  it("uses each column's own track and caps a column without one", () => {
    // WHEN
    const template = getGridTemplateColumns([
      { meta: { gridTrack: "2.5rem" } },
      {},
      { meta: { gridTrack: "minmax(12rem, 1fr)" } },
    ]);

    // THEN
    expect(template).toBe(`2.5rem fit-content(${COLUMN_MAX_WIDTH}) minmax(12rem, 1fr)`);
  });

  it("gives an empty template when there are no columns", () => {
    expect(getGridTemplateColumns([])).toBe("");
  });
});
