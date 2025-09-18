import { describe, expect, it } from "vitest";

import type { Filter } from "@/shared/hooks/useFilters";

import { FILTER_CONDITION } from "@/entities/nodes/object/ui/filters/filter-condition-select";

import { getCurrentFilterCondition } from "./get-current-filter-condition";

describe("getCurrentFilterCondition", () => {
  it("should return undefined when no filter is provided", () => {
    // GIVEN
    const filter = undefined;

    // WHEN
    const result = getCurrentFilterCondition(filter);

    // THEN
    expect(result).toBeUndefined();
  });

  it("should return CONTAINS condition for field__value filter", () => {
    // GIVEN
    const filter: Filter = { name: "field__value", value: "test" };

    // WHEN
    const result = getCurrentFilterCondition(filter);

    // THEN
    expect(result).toEqual(FILTER_CONDITION.CONTAINS);
  });

  it("should return IS_ANY_OF condition for field__ids filter", () => {
    // GIVEN
    const filter: Filter = { name: "field__ids", value: ["id1", "id2"] };

    // WHEN
    const result = getCurrentFilterCondition(filter);

    // THEN
    expect(result).toEqual(FILTER_CONDITION.IS_ANY_OF);
  });

  it("should return IS_ANY_OF condition for field__values filter", () => {
    // GIVEN
    const filter: Filter = { name: "field__values", value: ["value1", "value2"] };

    // WHEN
    const result = getCurrentFilterCondition(filter);

    // THEN
    expect(result).toEqual(FILTER_CONDITION.IS_ANY_OF);
  });

  it("should return IS_EMPTY condition for field__isnull filter with true value", () => {
    // GIVEN
    const filter: Filter = { name: "field__isnull", value: true };

    // WHEN
    const result = getCurrentFilterCondition(filter);

    // THEN
    expect(result).toEqual(FILTER_CONDITION.IS_EMPTY);
  });

  it("should return IS_NOT_EMPTY condition for field__isnull filter with false value", () => {
    // GIVEN
    const filter: Filter = { name: "field__isnull", value: false };

    // WHEN
    const result = getCurrentFilterCondition(filter);

    // THEN
    expect(result).toEqual(FILTER_CONDITION.IS_NOT_EMPTY);
  });

  it("should return undefined for filter with unknown condition suffix", () => {
    // GIVEN
    const filter: Filter = { name: "field__unknown", value: "test" };

    // WHEN
    const result = getCurrentFilterCondition(filter);

    // THEN
    expect(result).toBeUndefined();
  });

  it("should return undefined for filter with no condition suffix", () => {
    // GIVEN
    const filter: Filter = { name: "field", value: "test" } as unknown as Filter;

    // WHEN
    const result = getCurrentFilterCondition(filter);

    // THEN
    expect(result).toBeUndefined();
  });
});
