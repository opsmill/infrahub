import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchContext } from "@/entities/branches/ui/branches-provider";
import { useBranchTableRows } from "@/entities/branches/ui/hooks/use-branch-table-rows";
import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import {
  getBranchRepositories,
  getRepositoryListKind,
} from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

import { generateBranch } from "../../../../../tests/fake/branch";
import {
  generateBranchRepositoriesResult,
  generateBranchRepository,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";

vi.mock(
  "@/entities/repository/domain/use-cases/get-branch-repositories",
  async (importOriginal) => ({
    ...(await importOriginal<
      typeof import("@/entities/repository/domain/use-cases/get-branch-repositories")
    >()),
    getBranchRepositories: vi.fn(),
  })
);

const main = generateBranch({
  id: "branch-main",
  name: "main",
  is_default: true,
  sync_with_git: true,
});
const feature = generateBranch({ id: "branch-feature", name: "feature", sync_with_git: null });
const selectedBranch = generateBranch({ id: "branch-selected", name: "selected" });

const alpha = generateBranchRepository({ id: "repo-alpha", name: "alpha" });
const bravo = generateBranchRepository({ id: "repo-bravo", name: "bravo" });

const deferred = () => {
  let resolve!: (value: BranchRepositoriesResult) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<BranchRepositoriesResult>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const renderRows = (branches: BranchListItem[]) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(
        BranchContext,
        { value: { currentBranch: selectedBranch, setCurrentBranch: () => {} } },
        children
      )
    );
  return { queryClient, rendered: renderHook(() => useBranchTableRows(branches), { wrapper }) };
};

const byBranchName = (responses: Record<string, Promise<BranchRepositoriesResult>>) =>
  vi.mocked(getBranchRepositories).mockImplementation(({ branchName }) => {
    const response = responses[branchName];
    if (!response) throw new Error(`unexpected branch ${branchName}`);
    return response;
  });

beforeEach(() => {
  vi.mocked(getBranchRepositories).mockReset();
});

describe("useBranchTableRows", () => {
  test("runs one query per listed branch on the key shared with the branch details card", async () => {
    // GIVEN two branches, and a different branch selected in the branch selector
    byBranchName({
      main: Promise.resolve(generateBranchRepositoriesResult([alpha])),
      feature: Promise.resolve(generateBranchRepositoriesResult([])),
    });

    // WHEN the hook renders
    const { queryClient, rendered } = renderRows([main, feature]);
    const { result } = await rendered;

    // THEN each listed branch is fetched once with its own sync flag, and never the selected one
    await vi.waitFor(() => expect(result.current.map((row) => row.state)).toEqual(["ok", "empty"]));
    expect(getBranchRepositories).toHaveBeenCalledTimes(2);
    expect(getBranchRepositories).toHaveBeenCalledWith({ branchName: "main", syncWithGit: true });
    expect(getBranchRepositories).toHaveBeenCalledWith({
      branchName: "feature",
      syncWithGit: false,
    });
    expect(
      queryClient.getQueryData(
        repositoryQueryKeys.branch({ branchName: "main", kind: getRepositoryListKind(true) })
      )
    ).toEqual(generateBranchRepositoriesResult([alpha]));
    expect(
      queryClient.getQueryData(
        repositoryQueryKeys.branch({ branchName: "feature", kind: getRepositoryListKind(false) })
      )
    ).toEqual(generateBranchRepositoriesResult([]));
  });

  test("maps pending, then data or the error with its message", async () => {
    const mainResponse = deferred();
    const featureResponse = deferred();
    byBranchName({ main: mainResponse.promise, feature: featureResponse.promise });

    const { result } = await renderRows([main, feature]).rendered;
    expect(result.current.map((row) => row.state)).toEqual(["pending", "pending"]);

    mainResponse.resolve(generateBranchRepositoriesResult([alpha, bravo]));
    featureResponse.reject(new Error("Server exploded"));

    await vi.waitFor(() =>
      expect(result.current.map((row) => row.state)).toEqual(["ok", "ok", "error"])
    );
    expect(result.current[2]).toMatchObject({ id: feature.id, errorMessage: "Server exploded" });
  });

  test("keeps the loaded rows when a background refetch fails", async () => {
    byBranchName({ main: Promise.resolve(generateBranchRepositoriesResult([alpha])) });
    const { queryClient, rendered } = renderRows([main]);
    const { result } = await rendered;
    await vi.waitFor(() => expect(result.current[0]?.state).toBe("ok"));

    vi.mocked(getBranchRepositories).mockRejectedValueOnce(new Error("network is down"));
    await queryClient.refetchQueries();

    expect(
      queryClient.getQueryState(
        repositoryQueryKeys.branch({ branchName: "main", kind: getRepositoryListKind(true) })
      )?.status
    ).toBe("error");
    expect(result.current).toEqual([{ id: main.id, branch: main, state: "ok", repository: alpha }]);
  });

  test("reuses the other branches' row objects when one branch resolves", async () => {
    // GIVEN main has loaded and feature is still pending
    const featureResponse = deferred();
    byBranchName({
      main: Promise.resolve(generateBranchRepositoriesResult([alpha, bravo])),
      feature: featureResponse.promise,
    });
    const { result } = await renderRows([main, feature]).rendered;
    await vi.waitFor(() => expect(result.current[0]?.state).toBe("ok"));
    const [mainAnchor, mainSecond] = result.current;

    // WHEN feature resolves
    featureResponse.resolve(generateBranchRepositoriesResult([alpha]));
    await vi.waitFor(() => expect(result.current[2]?.state).toBe("ok"));

    // THEN main's rows are the very same objects
    expect(result.current[0]).toBe(mainAnchor);
    expect(result.current[1]).toBe(mainSecond);
  });

  test("keeps polling every 10 seconds while a repository is syncing", async () => {
    const syncing = generateBranchRepository({
      id: "repo-syncing",
      syncStatus: SYNC_STATUS.syncing,
    });
    byBranchName({ main: Promise.resolve(generateBranchRepositoriesResult([syncing])) });
    const { queryClient, rendered } = renderRows([main]);
    const { result } = await rendered;
    await vi.waitFor(() => expect(result.current[0]?.state).toBe("ok"));

    const query = queryClient.getQueryCache().find({
      queryKey: repositoryQueryKeys.branch({
        branchName: "main",
        kind: getRepositoryListKind(true),
      }),
    });
    const refetchInterval = query?.observers[0]?.options.refetchInterval;

    if (!query || typeof refetchInterval !== "function") throw new Error("no polling query");
    expect(refetchInterval(query)).toBe(10_000);
  });
});
