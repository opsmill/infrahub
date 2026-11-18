import { beforeEach, describe, expect, it, vi } from "vitest";

import { getRepositoryBranchStatusFromApi } from "@/entities/branch-git-status/api/get-repository-branch-status-from-api";
import { getRepositoryBranchStatus } from "@/entities/branch-git-status/domain/use-cases/get-repository-branch-status";

import { generateRepositoryBranchGitStatusWire } from "../../../../../tests/fake/branch-git-status";

vi.mock("@/entities/branch-git-status/api/get-repository-branch-status-from-api");

describe("getRepositoryBranchStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads the repository's status by id and maps the page", async () => {
    // GIVEN
    vi.mocked(getRepositoryBranchStatusFromApi).mockResolvedValue({
      count: 2,
      edges: [
        { node: generateRepositoryBranchGitStatusWire({ branchName: "main" }) },
        { node: generateRepositoryBranchGitStatusWire({ branchName: "feature" }) },
      ],
    });

    // WHEN
    const page = await getRepositoryBranchStatus({ repositoryId: "repo-1", limit: 500 });

    // THEN
    expect(getRepositoryBranchStatusFromApi).toHaveBeenCalledWith({ id: "repo-1", limit: 500 });
    expect(page.rows.map(({ branchName }) => branchName)).toEqual(["main", "feature"]);
    expect(page.count).toBe(2);
  });

  it("rejects with an UNKNOWN error that keeps the failure as its cause", async () => {
    // GIVEN
    const networkError = new TypeError("Failed to fetch");
    vi.mocked(getRepositoryBranchStatusFromApi).mockRejectedValue(networkError);

    // WHEN
    const result = getRepositoryBranchStatus({ repositoryId: "repo-1", limit: 500 });

    // THEN
    await expect(result).rejects.toMatchObject({
      name: "BranchGitStatusError",
      code: "UNKNOWN",
      cause: networkError,
    });
  });
});
