import { describe, expect, it } from "vitest";

import type {
  PushStatus,
  RepositoryPushState,
} from "@/entities/repository/domain/model/repository-push-state";
import { getRepositoryPushStateQueryOptions } from "@/entities/repository/ui/queries/get-repository-push-state.query";

const pushStateWith = (status: PushStatus): RepositoryPushState => ({
  status,
  statusLabel: status,
  statusColor: null,
  cause: null,
  causeLabel: null,
  error: null,
  pendingMerges: [],
  queueVersion: 0,
  lastAbandonedPush: null,
});

const refetchIntervalFor = (status: PushStatus | undefined, error: Error | null = null) => {
  const { refetchInterval } = getRepositoryPushStateQueryOptions({
    repositoryId: "repo-1",
    branchName: "main",
  });
  if (typeof refetchInterval !== "function") throw new Error("refetchInterval must be a function");
  const data = status === undefined ? undefined : pushStateWith(status);
  return refetchInterval({
    state: { data, error, status: error ? "error" : "success" },
  } as unknown as Parameters<typeof refetchInterval>[0]);
};

describe("getRepositoryPushStateQueryOptions", () => {
  it.each(["pending", "action-required"] as const)("polls every 10 seconds while %s", (status) => {
    expect(refetchIntervalFor(status)).toBe(10_000);
  });

  it("doesn't poll when nothing is pending or nothing has loaded", () => {
    expect(refetchIntervalFor("none")).toBe(false);
    expect(refetchIntervalFor(undefined)).toBe(false);
  });

  it("retries a failed read every minute", () => {
    expect(refetchIntervalFor(undefined, new Error("Offline"))).toBe(60_000);
  });
});
