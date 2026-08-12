import { describe, expect, test } from "vitest";

import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { computeProposedChangeSort } from "@/entities/proposed-changes/domain/rules/compute-proposed-change-sort";

describe("computeProposedChangeSort", () => {
  test("falls back to newest created first when nothing is applied", () => {
    // GIVEN
    const appliedSort: Sort[] = [];

    // WHEN
    const sort = computeProposedChangeSort(appliedSort);

    // THEN
    expect(sort).toEqual([{ field: "node_metadata__created_at", direction: "DESC" }]);
  });

  test("keeps the applied sort untouched", () => {
    // GIVEN
    const appliedSort: Sort[] = [{ field: "node_metadata__updated_at", direction: "ASC" }];

    // WHEN
    const sort = computeProposedChangeSort(appliedSort);

    // THEN
    expect(sort).toEqual(appliedSort);
  });
});
