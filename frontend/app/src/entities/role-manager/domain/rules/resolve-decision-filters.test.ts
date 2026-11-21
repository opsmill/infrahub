import { describe, expect, it } from "vitest";

import {
  globalDecisionOptions,
  objectDecisionOptions,
} from "@/entities/role-manager/domain/model/decision";

import { resolveDecisionFilters } from "./resolve-decision-filters";

describe("resolveDecisionFilters", () => {
  it("maps Allow label to numeric value 6", () => {
    // GIVEN
    const filters = [{ name: "decision__value", value: "Allow" }];

    // WHEN
    const result = resolveDecisionFilters(filters, globalDecisionOptions);

    // THEN
    expect(result).toEqual([{ name: "decision__value", value: 6 }]);
  });

  it("maps Deny label to numeric value 1", () => {
    // GIVEN
    const filters = [{ name: "decision__value", value: "Deny" }];

    // WHEN
    const result = resolveDecisionFilters(filters, globalDecisionOptions);

    // THEN
    expect(result).toEqual([{ name: "decision__value", value: 1 }]);
  });

  it("maps an object permission label with the object options", () => {
    // GIVEN
    const filters = [{ name: "decision__value", value: "Allow on other branches" }];

    // WHEN
    const result = resolveDecisionFilters(filters, objectDecisionOptions);

    // THEN
    expect(result).toEqual([{ name: "decision__value", value: 4 }]);
  });

  it("maps Deny everywhere to numeric value 1 with the object options", () => {
    // GIVEN
    const filters = [{ name: "decision__value", value: "Deny everywhere" }];

    // WHEN
    const result = resolveDecisionFilters(filters, objectDecisionOptions);

    // THEN
    expect(result).toEqual([{ name: "decision__value", value: 1 }]);
  });

  it("keeps a label that belongs only to the other option list", () => {
    // GIVEN
    const filters = [{ name: "decision__value", value: "Allow" }];

    // WHEN
    const result = resolveDecisionFilters(filters, objectDecisionOptions);

    // THEN
    expect(result).toEqual([{ name: "decision__value", value: "Allow" }]);
  });

  it("passes through non-decision filters unchanged", () => {
    // GIVEN
    const filters = [
      { name: "action__value", value: "create" },
      { name: "roles__ids", value: ["id1"] },
    ];

    // WHEN
    const result = resolveDecisionFilters(filters, globalDecisionOptions);

    // THEN
    expect(result).toEqual(filters);
  });

  it("handles mixed filters with decision and non-decision", () => {
    // GIVEN
    const filters = [
      { name: "action__value", value: "create" },
      { name: "decision__value", value: "Allow" },
    ];

    // WHEN
    const result = resolveDecisionFilters(filters, globalDecisionOptions);

    // THEN
    expect(result).toEqual([
      { name: "action__value", value: "create" },
      { name: "decision__value", value: 6 },
    ]);
  });

  it("preserves original value when label is unknown", () => {
    // GIVEN
    const filters = [{ name: "decision__value", value: "Unknown" }];

    // WHEN
    const result = resolveDecisionFilters(filters, globalDecisionOptions);

    // THEN
    expect(result).toEqual([{ name: "decision__value", value: "Unknown" }]);
  });

  it("returns empty array for empty input", () => {
    // GIVEN
    const filters: { name: string; value: unknown }[] = [];

    // WHEN
    const result = resolveDecisionFilters(filters, globalDecisionOptions);

    // THEN
    expect(result).toEqual([]);
  });
});
