import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { RepositoryActivityError } from "@/entities/repository/domain/model/repository-activity";
import { getRepositoryActivity } from "@/entities/repository/domain/use-cases/get-repository-activity";
import { getRepositoryActivityQueryOptions } from "@/entities/repository/ui/queries/get-repository-activity.query";
import {
  repositoriesQueryKeys,
  repositoryQueryKeys,
} from "@/entities/repository/ui/queries/repository.query-keys";

import { generateActiveRun, generateActivity } from "../../../../../tests/fake/repository-activity";

vi.mock("@/entities/repository/domain/use-cases/get-repository-activity");

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
    const error = new RepositoryActivityError("UNKNOWN", "Offline");

    expect(refetchIntervalFor({ data, error, status: "error" })).toBe(60_000);
  });

  it("stops checking once the viewer has no access", () => {
    const error = new RepositoryActivityError("NO_ACCESS", "Denied");

    expect(refetchIntervalFor({ error, status: "error" })).toBe(false);
  });
});

describe("getRepositoryActivityQueryOptions queryFn", () => {
  const getRepositoryActivityMock = vi.mocked(getRepositoryActivity);

  const fetchWith = async (previous: ReturnType<typeof generateActivity> | undefined) => {
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const options = getRepositoryActivityQueryOptions(PARAMS);
    if (previous) client.setQueryData(options.queryKey, previous);

    await client.fetchQuery(options);

    return invalidate.mock.calls.map(([filters]) => filters?.queryKey);
  };

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("refreshes the commits, branch statuses and object once a run has ended", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(generateActivity());

    // WHEN
    const refreshed = await fetchWith(generateActivity({ activeRuns: [generateActiveRun()] }));

    // THEN
    expect(refreshed).toEqual([
      repositoriesQueryKeys.repository({ repositoryId: "repository-1", branchName: "main" }),
      repositoryQueryKeys.branchStatuses(),
      objectQueryKeys.all,
    ]);
  });

  it("refreshes nothing while the same run goes on", async () => {
    // GIVEN
    const running = generateActivity({ activeRuns: [generateActiveRun()] });
    getRepositoryActivityMock.mockResolvedValue(running);

    // WHEN
    const refreshed = await fetchWith(running);

    // THEN
    expect(refreshed).toEqual([]);
  });

  it("refreshes nothing on the first answer", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(generateActivity());

    // WHEN
    const refreshed = await fetchWith(undefined);

    // THEN
    expect(refreshed).toEqual([]);
  });
});
