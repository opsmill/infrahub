import { describe, expect, test } from "vitest";

import { canRunGenerators } from "@/entities/generators/domain/rules/can-run-generators";

describe("canRunGenerators", () => {
  test("refuses a user who is not signed in on the default branch", () => {
    // WHEN
    const result = canRunGenerators({
      isAuthenticated: false,
      isDefaultBranch: true,
      hasEditDefaultBranch: true,
    });

    // THEN
    expect(result).toBe(false);
  });

  test("refuses a user who is not signed in on another branch", () => {
    // WHEN
    const result = canRunGenerators({
      isAuthenticated: false,
      isDefaultBranch: false,
      hasEditDefaultBranch: undefined,
    });

    // THEN
    expect(result).toBe(false);
  });

  test("allows a user who may edit the default branch on the default branch", () => {
    // WHEN
    const result = canRunGenerators({
      isAuthenticated: true,
      isDefaultBranch: true,
      hasEditDefaultBranch: true,
    });

    // THEN
    expect(result).toBe(true);
  });

  test("refuses a user who may not edit the default branch on the default branch", () => {
    // WHEN
    const result = canRunGenerators({
      isAuthenticated: true,
      isDefaultBranch: true,
      hasEditDefaultBranch: false,
    });

    // THEN
    expect(result).toBe(false);
  });

  test("refuses on the default branch while the permission is not known yet", () => {
    // WHEN
    const result = canRunGenerators({
      isAuthenticated: true,
      isDefaultBranch: true,
      hasEditDefaultBranch: undefined,
    });

    // THEN
    expect(result).toBe(false);
  });

  test("allows any signed-in user on another branch", () => {
    // WHEN
    const result = canRunGenerators({
      isAuthenticated: true,
      isDefaultBranch: false,
      hasEditDefaultBranch: false,
    });

    // THEN
    expect(result).toBe(true);
  });
});
