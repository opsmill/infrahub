import { describe, expect, test } from "vitest";

import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { serializeSortToken } from "@/entities/nodes/sort/domain/rules/sort-token";
import {
  PROPOSED_CHANGE_DEFAULT_SORT,
  PROPOSED_CHANGE_SORT_OPTIONS,
} from "@/entities/proposed-changes/domain/model/proposed-change-sort";
import {
  computeProposedChangeSort,
  isProposedChangeDefaultSort,
  isProposedChangeSortedByUpdatedAt,
} from "@/entities/proposed-changes/domain/rules/proposed-change-sort";

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

describe("PROPOSED_CHANGE_SORT_OPTIONS", () => {
  // The menu keys its items by sort token, so two options sharing one would collide.
  test("each option offers a distinct order", () => {
    // GIVEN
    const options = PROPOSED_CHANGE_SORT_OPTIONS;

    // WHEN
    const tokens = options.map((option) => serializeSortToken(option.sort));

    // THEN
    expect(new Set(tokens).size).toBe(options.length);
  });
});

describe("isProposedChangeSortedByUpdatedAt", () => {
  test("is true when the update date drives the order", () => {
    // GIVEN
    const sort: Sort[] = [{ field: "node_metadata__updated_at", direction: "DESC" }];

    // WHEN
    const isSortedByUpdatedAt = isProposedChangeSortedByUpdatedAt(sort);

    // THEN
    expect(isSortedByUpdatedAt).toBe(true);
  });

  test("is false when the update date is only a secondary key", () => {
    // GIVEN
    const sort: Sort[] = [
      { field: "name__value", direction: "ASC" },
      { field: "node_metadata__updated_at", direction: "DESC" },
    ];

    // WHEN
    const isSortedByUpdatedAt = isProposedChangeSortedByUpdatedAt(sort);

    // THEN
    expect(isSortedByUpdatedAt).toBe(false);
  });

  test("is false for the default order", () => {
    // GIVEN
    const sort = computeProposedChangeSort([]);

    // WHEN
    const isSortedByUpdatedAt = isProposedChangeSortedByUpdatedAt(sort);

    // THEN
    expect(isSortedByUpdatedAt).toBe(false);
  });
});

describe("isProposedChangeDefaultSort", () => {
  test("is true for newest created first", () => {
    // GIVEN
    const sort = PROPOSED_CHANGE_DEFAULT_SORT;

    // WHEN
    const isDefault = isProposedChangeDefaultSort(sort);

    // THEN
    expect(isDefault).toBe(true);
  });

  test("is false when only the direction differs", () => {
    // GIVEN
    const sort: Sort = { field: "node_metadata__created_at", direction: "ASC" };

    // WHEN
    const isDefault = isProposedChangeDefaultSort(sort);

    // THEN
    expect(isDefault).toBe(false);
  });
});
