import { describe, expect, it } from "vitest";

import { getRepositoryActivityQueryOptions } from "@/entities/repository/ui/queries/get-repository-activity.query";

import { generateActiveRun, generateActivity } from "../../../../../tests/fake/repository-activity";

const PARAMS = { id: "repository-1", branchName: "main" };

const refetchIntervalFor = (state: { data?: unknown; error?: Error | null; status: string }) => {
  const { refetchInterval } = getRepositoryActivityQueryOptions(PARAMS);
  if (typeof refetchInterval !== "function") throw new Error("refetchInterval must be a function");
  return refetchInterval({ state: { error: null, ...state } } as unknown as Parameters<
    typeof refetchInterval
  >[0]);
};

describe("getRepositoryActivityQueryOptions refetchInterval", () => {
  it("checks every 5 seconds while a run is active", () => {
    const data = generateActivity({ activeRuns: [generateActiveRun()] });

    expect(refetchIntervalFor({ data, status: "success" })).toBe(5000);
  });

  it("checks every 30 seconds while the repository is idle, to notice a run started elsewhere", () => {
    expect(refetchIntervalFor({ data: generateActivity(), status: "success" })).toBe(30_000);
  });

  it("checks every minute after a failure, even with a run shown before it", () => {
    const data = generateActivity({ activeRuns: [generateActiveRun()] });
    const error = new Error("Offline");

    expect(refetchIntervalFor({ data, error, status: "error" })).toBe(60_000);
  });
});
