import { describe, expect, test } from "vitest";

import { getRepositoryLocation } from "@/entities/repository/domain/rules/get-repository-location";

describe("getRepositoryLocation", () => {
  test("returns the location attribute's string value", () => {
    expect(
      getRepositoryLocation({ location: { value: "https://github.com/opsmill/infrahub" } })
    ).toBe("https://github.com/opsmill/infrahub");
  });

  test("returns null when the location attribute is missing", () => {
    expect(getRepositoryLocation({})).toBeNull();
  });

  test("returns null when the location value is null", () => {
    expect(getRepositoryLocation({ location: { value: null } })).toBeNull();
  });

  test("returns null when the location value is not a string", () => {
    expect(getRepositoryLocation({ location: { value: 42 } })).toBeNull();
  });
});
