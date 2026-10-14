import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { BranchContext } from "@/entities/branches/ui/branches-provider";
import type { RepositoryActivity } from "@/entities/repository/domain/model/repository-activity";
import { getRepositoryActivity } from "@/entities/repository/domain/use-cases/get-repository-activity";
import { useRefreshAfterRepositoryRun } from "@/entities/repository/ui/hooks/use-refresh-after-repository-run";
import {
  repositoriesQueryKeys,
  repositoryQueryKeys,
} from "@/entities/repository/ui/queries/repository.query-keys";

import { generateBranch } from "../../../../../tests/fake/branch";
import {
  generateActiveRun,
  generateActivity,
  generateLastRun,
} from "../../../../../tests/fake/repository-activity";

vi.mock("@/entities/repository/domain/use-cases/get-repository-activity");

const REPOSITORY_ID = "repository-1";
const BRANCH = generateBranch({ name: "main" });

const COMMITS_KEY = [
  ...repositoriesQueryKeys.repository({ repositoryId: REPOSITORY_ID, branchName: "main" }),
  "commits",
];
const BRANCH_STATUS_KEY = [...repositoryQueryKeys.branchStatuses(), { id: REPOSITORY_ID }];
const REPOSITORY_OBJECT_KEY = ["objects", "main", null, "CoreRepository", REPOSITORY_ID];
const OTHER_OBJECT_KEY = ["objects", "main", null, "InfraDevice", "device-1"];
const SEEDED_KEYS = [COMMITS_KEY, BRANCH_STATUS_KEY, REPOSITORY_OBJECT_KEY, OTHER_OBJECT_KEY];

const SYNC_AT_10 = generateLastRun({ operation: "SYNC", finishedAt: "2026-10-14T10:00:00Z" });
const SYNC_AT_14 = generateLastRun({ operation: "SYNC", finishedAt: "2026-10-14T14:00:00Z" });

const renderRefresh = async (firstAnswer: RepositoryActivity) => {
  vi.mocked(getRepositoryActivity).mockResolvedValue(firstAnswer);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  for (const queryKey of SEEDED_KEYS) queryClient.setQueryData(queryKey, {});

  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(
        BranchContext,
        { value: { currentBranch: BRANCH, setCurrentBranch: () => {} } },
        children
      )
    );
  await renderHook(() => useRefreshAfterRepositoryRun({ repositoryId: REPOSITORY_ID }), {
    wrapper,
  });
  const activityKey = repositoriesQueryKeys.activity({ repositoryId: REPOSITORY_ID });
  await vi.waitFor(() => expect(queryClient.getQueryData(activityKey)).toEqual(firstAnswer));

  // Each answer needs a render of its own, as polls arrive seconds apart, not in one batch.
  const settle = () => new Promise((resolve) => setTimeout(resolve, 50));
  await settle();

  const answer = async (next: RepositoryActivity) => {
    queryClient.setQueryData(activityKey, next);
    await settle();
  };
  const invalidatedKeys = () =>
    SEEDED_KEYS.filter((queryKey) => queryClient.getQueryState(queryKey)?.isInvalidated);

  return { answer, invalidatedKeys };
};

describe("useRefreshAfterRepositoryRun", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("refreshes the commits, branch statuses and this repository's details when a run finishes", async () => {
    // GIVEN
    const { answer, invalidatedKeys } = await renderRefresh(
      generateActivity({ activeRuns: [generateActiveRun()], lastRuns: [SYNC_AT_10] })
    );

    // WHEN
    await answer(generateActivity({ lastRuns: [SYNC_AT_14] }));

    // THEN
    expect(invalidatedKeys()).toEqual([COMMITS_KEY, BRANCH_STATUS_KEY, REPOSITORY_OBJECT_KEY]);
  });

  it("refreshes them for a run that started and finished between two checks", async () => {
    // GIVEN
    const { answer, invalidatedKeys } = await renderRefresh(
      generateActivity({ lastRuns: [SYNC_AT_10] })
    );

    // WHEN
    await answer(generateActivity({ lastRuns: [SYNC_AT_14] }));

    // THEN
    expect(invalidatedKeys()).toEqual([COMMITS_KEY, BRANCH_STATUS_KEY, REPOSITORY_OBJECT_KEY]);
  });

  it("refreshes them when the first recorded run finishes", async () => {
    // GIVEN
    const { answer, invalidatedKeys } = await renderRefresh(generateActivity());

    // WHEN
    await answer(generateActivity({ lastRuns: [SYNC_AT_14] }));

    // THEN
    expect(invalidatedKeys()).toEqual([COMMITS_KEY, BRANCH_STATUS_KEY, REPOSITORY_OBJECT_KEY]);
  });

  it("refreshes nothing while no run has finished", async () => {
    // GIVEN
    const { answer, invalidatedKeys } = await renderRefresh(
      generateActivity({ activeRuns: [generateActiveRun()], lastRuns: [SYNC_AT_10] })
    );

    // WHEN
    await answer(generateActivity({ activeRuns: [generateActiveRun()], lastRuns: [SYNC_AT_10] }));

    // THEN
    expect(invalidatedKeys()).toEqual([]);
  });

  it("refreshes nothing on the first answer after the page loads", async () => {
    // GIVEN
    const firstAnswer = generateActivity({ lastRuns: [SYNC_AT_14] });

    // WHEN
    const { invalidatedKeys } = await renderRefresh(firstAnswer);

    // THEN
    expect(invalidatedKeys()).toEqual([]);
  });
});
