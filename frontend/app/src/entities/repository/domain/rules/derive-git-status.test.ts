import { describe, expect, it } from "vitest";

import {
  type DeriveGitStatusInput,
  deriveGitStatus,
} from "@/entities/repository/domain/rules/derive-git-status";

const settled: DeriveGitStatusInput = {
  totalIsPending: false,
  totalError: null,
  totalCount: 3,
  failingIsPending: false,
  failingError: null,
  failingCount: 0,
};

describe("deriveGitStatus", () => {
  it("returns loading while the total lookup is still pending", () => {
    // GIVEN
    const input: DeriveGitStatusInput = { ...settled, totalIsPending: true, totalCount: undefined };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("loading");
  });

  it("returns loading while the failing lookup is still pending", () => {
    // GIVEN
    const input: DeriveGitStatusInput = {
      ...settled,
      failingIsPending: true,
      failingCount: undefined,
    };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("loading");
  });

  it("returns loading rather than error when a failure is known but a lookup is still pending", () => {
    // GIVEN
    const input: DeriveGitStatusInput = {
      ...settled,
      totalIsPending: true,
      totalCount: undefined,
      failingCount: 2,
    };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("loading");
  });

  it("returns check-failed when the total lookup errored", () => {
    // GIVEN
    const input: DeriveGitStatusInput = {
      ...settled,
      totalError: new Error("boom"),
      totalCount: undefined,
    };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("check-failed");
  });

  it("returns inert when the branch has no repositories and the failing lookup errored", () => {
    // GIVEN a branch with no repositories, so the failing count is necessarily zero and its
    // failed lookup cannot change the answer
    const input: DeriveGitStatusInput = {
      ...settled,
      totalCount: 0,
      failingError: new Error("boom"),
      failingCount: undefined,
    };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("inert");
  });

  it("returns check-failed when the failing lookup errored and repositories exist", () => {
    // GIVEN
    const input: DeriveGitStatusInput = {
      ...settled,
      totalCount: 3,
      failingError: new Error("boom"),
      failingCount: undefined,
    };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("check-failed");
  });

  it("returns inert when the branch has no repositories", () => {
    // GIVEN
    const input: DeriveGitStatusInput = { ...settled, totalCount: 0, failingCount: 0 };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("inert");
  });

  it("returns error when at least one repository is failing", () => {
    // GIVEN
    const input: DeriveGitStatusInput = { ...settled, totalCount: 3, failingCount: 1 };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("error");
  });

  it("returns error, with no special treatment, when every repository is failing", () => {
    // GIVEN
    const input: DeriveGitStatusInput = { ...settled, totalCount: 3, failingCount: 3 };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("error");
  });

  it("returns neutral when repositories exist and none are failing", () => {
    // GIVEN
    const input: DeriveGitStatusInput = { ...settled, totalCount: 3, failingCount: 0 };

    // WHEN
    const status = deriveGitStatus(input);

    // THEN
    expect(status).toBe("neutral");
  });
});
