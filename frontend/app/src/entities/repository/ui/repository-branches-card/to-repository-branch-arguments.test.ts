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

  it("offers only conditions every active filter can be mapped from", () => {
    // GIVEN a filter the toolbar counts as active
    const filters: Filter[] = [{ name: "name__isnull", value: true }];

    // THEN the emptiness condition that produced it is not one the toolbar can offer, so no filter
    // the user is able to set can be counted as active and then dropped from the request
    expect(hasRepositoryBranchFilters(filters)).toBe(true);
    expect(toRepositoryBranchArguments(filters, [])).toEqual({});
    expect(BRANCH_ROW_FILTER_CONDITIONS).toEqual(["contains"]);
  });
});
