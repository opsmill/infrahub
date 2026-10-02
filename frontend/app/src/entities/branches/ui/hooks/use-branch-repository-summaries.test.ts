import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { useBranchRepositorySummaries } from "@/entities/branches/ui/hooks/use-branch-repository-summaries";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import {
  mapRepositoryBranchStatusRow,
  RepositoryBranchStatusError,
  type RepositoryBranchStatusPage,
} from "@/entities/repository/domain/model/repository-branch-status";
import { getBranchRepositories } from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { getRepositoryBranchStatus } from "@/entities/repository/domain/use-cases/get-repository-branch-status";
import { getRepositoryBranchStatusQueryOptions } from "@/entities/repository/ui/queries/get-repository-branch-status.query";

import { generateBranch } from "../../../../../tests/fake/branch";
import {
  generateBranchRepository,
  toBranchRepositoryPage,
} from "../../../../../tests/fake/branch-repositories";
import { generateDropdown } from "../../../../../tests/fake/dropdown";
import { generateRepositoryBranchStatus } from "../../../../../tests/fake/repository";

vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock(
  "@/entities/repository/domain/use-cases/get-branch-repositories",
  async (importOriginal) => ({
    ...(await importOriginal<
      typeof import("@/entities/repository/domain/use-cases/get-branch-repositories")
    >()),
    getBranchRepositories: vi.fn(),
  })
);
vi.mock("@/entities/repository/domain/use-cases/get-repository-branch-status");

const primary = generateBranch({ id: "b-primary", name: "primary", is_default: true });
const feature = generateBranch({ id: "b-feature", name: "feature", sync_with_git: true });

const SYNCING = generateDropdown({ value: "syncing", label: "Syncing" });

const pageOf = (...names: string[]): RepositoryBranchStatusPage => ({
  rows: names.map((name) =>
    mapRepositoryBranchStatusRow(generateRepositoryBranchStatus({ name: { value: name } }))
  ),
  count: names.length,
});

const renderSummaries = async () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  const rendered = await renderHook(() => useBranchRepositorySummaries([primary, feature]), {
    wrapper,
  });
  return { queryClient, result: rendered.result };
};

describe("useBranchRepositorySummaries", () => {
  beforeEach(() => {
    vi.mocked(useGetBranches).mockReturnValue({
      data: [feature, primary],
    } as unknown as ReturnType<typeof useGetBranches>);
    vi.mocked(getBranchRepositories).mockResolvedValue(
      toBranchRepositoryPage(
        [
          generateBranchRepository({ id: "repo-1", name: "repo-one" }),
          generateBranchRepository({ id: "repo-2", name: "repo-two" }),
        ],
        { limit: 500 }
      )
    );
    vi.mocked(getRepositoryBranchStatus).mockResolvedValue(pageOf("primary", "feature"));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("lists repositories once on the default branch and reads each one's status once", async () => {
    // WHEN
    const { result } = await renderSummaries();

    // THEN
    await expect.poll(() => result.current.feature?.status).toBe("ok");
    expect(vi.mocked(getBranchRepositories).mock.calls).toEqual([
      [{ branchName: "primary", syncWithGit: true, limit: 500, offset: 0 }],
    ]);
    expect(vi.mocked(getRepositoryBranchStatus).mock.calls.map(([params]) => params)).toEqual([
      { id: "repo-1", branchName: "primary", limit: 500 },
      { id: "repo-2", branchName: "primary", limit: 500 },
    ]);
  });

  test("keys the summaries by branch name", async () => {
    // WHEN
    const { result } = await renderSummaries();

    // THEN
    await expect.poll(() => result.current.primary?.status).toBe("ok");
    expect(Object.keys(result.current)).toEqual(["primary", "feature"]);
    expect(result.current.feature).toMatchObject({
      repositories: [{ repository: { id: "repo-1" } }, { repository: { id: "repo-2" } }],
    });
  });

  test("is pending until the repository list has loaded", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockReturnValue(new Promise(() => {}));

    // WHEN
    const { result } = await renderSummaries();

    // THEN
    expect(result.current).toEqual({
      primary: { status: "pending" },
      feature: { status: "pending" },
    });
    expect(getRepositoryBranchStatus).not.toHaveBeenCalled();
  });

  test("keeps the loaded summary when a background refetch fails", async () => {
    // GIVEN
    const { result, queryClient } = await renderSummaries();
    await expect.poll(() => result.current.feature?.status).toBe("ok");
    vi.mocked(getRepositoryBranchStatus).mockRejectedValue(new Error("network is down"));

    // WHEN
    await queryClient.refetchQueries({ type: "active" });

    // THEN
    await expect
      .poll(
        () =>
          queryClient.getQueryCache().findAll({ predicate: (q) => q.state.status === "error" })
            .length
      )
      .toBe(2);
    expect(result.current.feature?.status).toBe("ok");
  });

  test("marks every branch denied when a status read is denied", async () => {
    // GIVEN
    vi.mocked(getRepositoryBranchStatus).mockRejectedValue(
      new RepositoryBranchStatusError("PERMISSION_DENIED", "denied")
    );

    // WHEN
    const { result } = await renderSummaries();

    // THEN
    await expect
      .poll(() => result.current)
      .toEqual({ primary: { status: "denied" }, feature: { status: "denied" } });
  });

  test("carries any other status failure as an error", async () => {
    // GIVEN
    vi.mocked(getRepositoryBranchStatus).mockRejectedValue(
      new RepositoryBranchStatusError("UNKNOWN", "Repository index unavailable")
    );

    // WHEN
    const { result } = await renderSummaries();

    // THEN
    await expect
      .poll(() => result.current.feature)
      .toEqual({ status: "error", message: "Repository index unavailable" });
  });
});

describe("getRepositoryBranchStatusQueryOptions", () => {
  const options = getRepositoryBranchStatusQueryOptions({
    id: "repo-1",
    branchName: "primary",
    limit: 500,
  });

  const refetchIntervalFor = (data: RepositoryBranchStatusPage | undefined) => {
    const { refetchInterval } = options;
    if (typeof refetchInterval !== "function")
      throw new Error("refetchInterval must be a function");
    return refetchInterval({ state: { data } } as unknown as Parameters<typeof refetchInterval>[0]);
  };

  test("keeps the status fresh for a minute", () => {
    expect(options.staleTime).toBe(60_000);
  });

  test("polls every 10 seconds only while a row is syncing", () => {
    const syncing: RepositoryBranchStatusPage = {
      rows: [
        ...pageOf("primary").rows,
        mapRepositoryBranchStatusRow(
          generateRepositoryBranchStatus({ name: { value: "feature" }, sync_status: SYNCING })
        ),
      ],
      count: 2,
    };

    expect(refetchIntervalFor(syncing)).toBe(10_000);
    expect(refetchIntervalFor(pageOf("primary", "feature"))).toBe(false);
    expect(refetchIntervalFor(undefined)).toBe(false);
  });

  test("reports an error on every branch when the repository list itself was cut short", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockResolvedValue({
      repositories: [generateBranchRepository({ id: "repo-1", name: "one" })],
      count: 501,
    });

    // WHEN
    const { result } = await renderSummaries();

    // THEN
    await vi.waitFor(() => expect(result.current.primary?.status).toBe("error"));
    expect(result.current.feature).toMatchObject({
      status: "error",
      message: expect.stringContaining("first 1 of 501 repositories"),
    });
  });
});
