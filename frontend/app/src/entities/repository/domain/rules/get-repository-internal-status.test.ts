import { describe, expect, test } from "vitest";

import { getRepositoryInternalStatus } from "@/entities/repository/domain/rules/get-repository-internal-status";

describe("getRepositoryInternalStatus", () => {
  test("returns the internal status attribute's string value", () => {
    expect(getRepositoryInternalStatus({ internal_status: { value: "staging" } })).toBe("staging");
  });

  test("returns null when the internal status attribute is missing", () => {
    expect(getRepositoryInternalStatus({})).toBeNull();
  });

  test("returns null when the internal status value is null", () => {
    expect(getRepositoryInternalStatus({ internal_status: { value: null } })).toBeNull();
  });
});
