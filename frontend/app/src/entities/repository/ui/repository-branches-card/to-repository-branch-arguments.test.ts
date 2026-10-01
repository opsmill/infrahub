import { describe, expect, it } from "vitest";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import {
  NODE_METADATA_SORT_FIELDS,
  SORT_DIRECTION,
  type Sort,
} from "@/entities/nodes/sort/domain/model/sort";
import { BRANCH_ROW_FILTER_CONDITIONS } from "@/entities/repository/ui/repository-branches-card/branch-row-fields";
import {
  hasRepositoryBranchFilters,
  toRepositoryBranchArguments,
} from "@/entities/repository/ui/repository-branches-card/to-repository-branch-arguments";

const [CREATED_AT, UPDATED_AT] = NODE_METADATA_SORT_FIELDS;

describe("toRepositoryBranchArguments", () => {
  it("orders by the first timestamp alone when both are sorted on", () => {
    // GIVEN the server refuses an order naming both timestamps
    const sorts: Sort[] = [
      { field: UPDATED_AT, direction: SORT_DIRECTION.ASC },
      { field: CREATED_AT, direction: SORT_DIRECTION.DESC },
    ];

    // WHEN
    const result = toRepositoryBranchArguments([], sorts);

    // THEN
    expect(result.order).toEqual({ node_metadata: { updated_at: "ASC" } });
  });

  it("orders by the one timestamp that is sorted on", () => {
    // WHEN
    const result = toRepositoryBranchArguments([], [
      { field: CREATED_AT, direction: SORT_DIRECTION.DESC },
    ] satisfies Sort[]);

    // THEN
    expect(result.order).toEqual({ node_metadata: { created_at: "DESC" } });
  });

  it("sends no order argument when nothing is sorted", () => {
    // THEN
    expect(toRepositoryBranchArguments([], [])).toEqual({});
  });

  it("maps a name fragment and a status onto the arguments the contract takes", () => {
    // GIVEN
    const filters: Filter[] = [
      { name: "name__value", value: "release" },
      { name: "status__value", value: "OPEN" },
    ];

    // WHEN
    const result = toRepositoryBranchArguments(filters, []);

    // THEN
    expect(result).toEqual({
      name__value: "release",
      partial_match: true,
      status__value: "OPEN",
    });
  });

  it.each([
    ["an emptiness filter", { name: "name__isnull", value: true }],
    ["a multi-value filter", { name: "name__values", value: ["main", "staging"] }],
    ["a field the contract cannot narrow on", { name: "description__value", value: "anything" }],
  ])("does not count %s the request cannot apply as active", (_label, filter) => {
    // GIVEN a filter that reached the url from somewhere this card's controls cannot produce
    const filters: Filter[] = [filter];

    // THEN an empty result must not claim it was narrowed by something never sent
    expect(toRepositoryBranchArguments(filters, [])).toEqual({});
    expect(hasRepositoryBranchFilters(filters)).toBe(false);
  });

  it("counts a filter the request does apply as active", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "status__value", value: "OPEN" }];

    // THEN
    expect(hasRepositoryBranchFilters(filters)).toBe(true);
    expect(BRANCH_ROW_FILTER_CONDITIONS).toEqual(["contains"]);
  });
});
