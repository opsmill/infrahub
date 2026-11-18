import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { BranchGitRepositoryPage } from "@/entities/branch-git-status/domain/model/branch-git-repository";
import { BranchGitStatusError } from "@/entities/branch-git-status/domain/model/branch-git-status";
import { getBranchGitRepositories } from "@/entities/branch-git-status/domain/use-cases/get-branch-git-repositories";
import { getRepositoryBranchStatus } from "@/entities/branch-git-status/domain/use-cases/get-repository-branch-status";
import { useGetBranchGitStatuses } from "@/entities/branch-git-status/ui/hooks/use-get-branch-git-statuses";

import {
  generateBranchGitRepository,
  generateRepositoryBranchGitStatus,
  generateRepositoryBranchGitStatusPage,
} from "../../../../../tests/fake/branch-git-status";

vi.mock("@/entities/branch-git-status/domain/use-cases/get-branch-git-repositories");
vi.mock("@/entities/branch-git-status/domain/use-cases/get-repository-branch-status");

const REPOSITORY_ONE = generateBranchGitRepository({ id: "repo-1", name: "repo-one" });
const REPOSITORY_TWO = generateBranchGitRepository({ id: "repo-2", name: "repo-two" });
const REPOSITORIES: BranchGitRepositoryPage = {
  repositories: [REPOSITORY_ONE, REPOSITORY_TWO],
  count: 2,
};

const renderStatuses = async (branchNames = ["primary", "feature"]) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  const rendered = await renderHook(() => useGetBranchGitStatuses(branchNames), { wrapper });
  return { queryClient, result: rendered.result };
};

describe("useGetBranchGitStatuses", () => {
  beforeEach(() => {
    vi.mocked(getBranchGitRepositories).mockResolvedValue(REPOSITORIES);
    vi.mocked(getRepositoryBranchStatus).mockResolvedValue(
      generateRepositoryBranchGitStatusPage({ branchNames: ["primary", "feature"] })
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("lists repositories once and reads each one's status once, keyed by branch name", async () => {
    // WHEN
    const { result } = await renderStatuses();

    // THEN
    await expect.poll(() => result.current.feature?.status).toBe("ok");
    expect(Object.keys(result.current)).toEqual(["primary", "feature"]);
    expect(vi.mocked(getBranchGitRepositories).mock.calls).toEqual([[{ limit: 500, offset: 0 }]]);
    expect(vi.mocked(getRepositoryBranchStatus).mock.calls).toEqual([
      [{ repositoryId: "repo-1", limit: 500 }],
      [{ repositoryId: "repo-2", limit: 500 }],
    ]);
  });

  test("keeps an unchanged branch's status object when another branch's status changes", async () => {
    // GIVEN
    const { queryClient, result } = await renderStatuses();
    await expect.poll(() => result.current.feature?.status).toBe("ok");
    const primaryBefore = result.current.primary;
    const featureBefore = result.current.feature;
    vi.mocked(getRepositoryBranchStatus).mockResolvedValue({
      rows: [
        generateRepositoryBranchGitStatus({ branchName: "primary" }),
        generateRepositoryBranchGitStatus({ branchName: "feature", commit: "new" }),
      ],
      count: 2,
    });

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    await expect.poll(() => result.current.feature).not.toBe(featureBefore);
    expect(result.current.feature).toMatchObject({
      status: "ok",
      repositories: [{ commit: "new" }, { commit: "new" }],
    });
    expect(result.current.primary).toBe(primaryBefore);
  });

  test("stays pending and reads no status until the repository list has loaded", async () => {
    // GIVEN
    let resolveList: (page: BranchGitRepositoryPage) => void = () => {};
    vi.mocked(getBranchGitRepositories).mockReturnValue(
      new Promise((resolve) => {
        resolveList = resolve;
      })
    );
    const { result } = await renderStatuses();
    expect(result.current.feature).toEqual({ status: "pending" });
    expect(getRepositoryBranchStatus).not.toHaveBeenCalled();

    // WHEN
    resolveList(REPOSITORIES);

    // THEN
    await expect.poll(() => result.current.feature?.status).toBe("ok");
    expect(getRepositoryBranchStatus).toHaveBeenCalledTimes(2);
  });

  test("keeps the loaded status when a background refetch fails", async () => {
    // GIVEN
    const { result, queryClient } = await renderStatuses();
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

  test("marks every branch denied when the repository list is denied, and reads no status", async () => {
    // GIVEN
    vi.mocked(getBranchGitRepositories).mockRejectedValue(
      new BranchGitStatusError("PERMISSION_DENIED", "denied")
    );

    // WHEN
    const { result } = await renderStatuses();

    // THEN
    await expect
      .poll(() => result.current)
      .toEqual({ primary: { status: "denied" }, feature: { status: "denied" } });
    expect(getRepositoryBranchStatus).not.toHaveBeenCalled();
  });

  test("reports the repository list's failure on every branch", async () => {
    // GIVEN
    vi.mocked(getBranchGitRepositories).mockRejectedValue(
      new BranchGitStatusError("UNKNOWN", "Repository list unavailable")
    );

    // WHEN
    const { result } = await renderStatuses();

    // THEN
    await expect
      .poll(() => result.current.primary)
      .toEqual({ status: "error", message: "Repository list unavailable" });
    expect(result.current.feature).toEqual(result.current.primary);
  });

  test("reads a permission error on every status read as denied", async () => {
    // GIVEN
    vi.mocked(getRepositoryBranchStatus).mockRejectedValue(
      new BranchGitStatusError("PERMISSION_DENIED", "denied")
    );

    // WHEN
    const { result } = await renderStatuses();

    // THEN
    await expect
      .poll(() => result.current)
      .toEqual({ primary: { status: "denied" }, feature: { status: "denied" } });
  });

  test("shows the other repositories and carries the one whose status read failed", async () => {
    // GIVEN
    vi.mocked(getRepositoryBranchStatus).mockImplementation(async ({ repositoryId }) => {
      if (repositoryId === "repo-2") {
        throw new BranchGitStatusError("UNKNOWN", "Repository index unavailable");
      }
      return generateRepositoryBranchGitStatusPage({ branchNames: ["primary", "feature"] });
    });

    // WHEN
    const { result } = await renderStatuses();

    // THEN
    await expect.poll(() => result.current.feature?.status).toBe("ok");
    expect(result.current.feature).toMatchObject({
      repositories: [{ repository: { id: "repo-1" } }],
      unloaded: [
        { status: "error", repository: REPOSITORY_TWO, message: "Repository index unavailable" },
      ],
    });
  });

  test("gives no status when there are no branches", async () => {
    // WHEN
    const { result } = await renderStatuses([]);

    // THEN
    await expect.poll(() => getRepositoryBranchStatus).toHaveBeenCalledTimes(2);
    expect(result.current).toEqual({});
  });

  test("reports an error on every branch when the repository list itself was cut short", async () => {
    // GIVEN
    vi.mocked(getBranchGitRepositories).mockResolvedValue({
      repositories: [REPOSITORY_ONE],
      count: 501,
    });

    // WHEN
    const { result } = await renderStatuses();

    // THEN
    await expect.poll(() => result.current.primary?.status).toBe("error");
    expect(result.current.feature).toEqual({
      status: "error",
      message: "Only the first 1 of 501 repositories were read. Open the branch for the full list.",
    });
    expect(getRepositoryBranchStatus).not.toHaveBeenCalled();
  });
});
