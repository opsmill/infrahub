import { describe, expect, it } from "vitest";

import {
  type DeriveRepositorySyncIndicatorInput,
  deriveRepositorySyncIndicator,
} from "@/entities/repository/domain/rules/derive-repository-sync-indicator";

const settled: DeriveRepositorySyncIndicatorInput = {
  totalIsPending: false,
  totalError: null,
  totalCount: 3,
  failingIsPending: false,
  failingError: null,
  failingCount: 0,
};

describe("deriveRepositorySyncIndicator", () => {
  it("returns loading while the total lookup is still pending", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalIsPending: true,
      totalCount: undefined,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("loading");
  });

  it("returns loading while the failing lookup is still pending", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      failingIsPending: true,
      failingCount: undefined,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("loading");
  });

  it("returns loading rather than failing when a failure is known but a lookup is still pending", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalIsPending: true,
      totalCount: undefined,
      failingCount: 2,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("loading");
  });

  it("returns check-failed when the total lookup errored", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalError: new Error("boom"),
      totalCount: undefined,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("check-failed");
  });

  it("returns no-repositories when the branch has no repositories and the failing lookup errored", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalCount: 0,
      failingError: new Error("boom"),
      failingCount: undefined,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("no-repositories");
  });

  it("returns check-failed when the failing lookup errored and repositories exist", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalCount: 3,
      failingError: new Error("boom"),
      failingCount: undefined,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("check-failed");
  });

  it("returns no-repositories when the total is zero and the failing lookup is still pending", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalCount: 0,
      failingIsPending: true,
      failingCount: undefined,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("no-repositories");
  });

  it("returns no-repositories when the branch has no repositories", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalCount: 0,
      failingCount: 0,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("no-repositories");
  });

  it("returns failing when at least one repository is failing", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalCount: 3,
      failingCount: 1,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("failing");
  });

  it("returns failing, with no special treatment, when every repository is failing", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalCount: 3,
      failingCount: 3,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("failing");
  });

  it("returns in-sync when repositories exist and none are failing", () => {
    // GIVEN
    const input: DeriveRepositorySyncIndicatorInput = {
      ...settled,
      totalCount: 3,
      failingCount: 0,
    };

    // WHEN
    const status = deriveRepositorySyncIndicator(input);

    // THEN
    expect(status).toBe("in-sync");
  });
});
