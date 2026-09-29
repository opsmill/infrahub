import { beforeEach, describe, expect, it, vi } from "vitest";

import { getBranchRepositoriesFromApi } from "@/entities/repository/api/get-branch-repositories-from-api";
import { getBranchRepositories } from "@/entities/repository/domain/use-cases/get-branch-repositories";

vi.mock("@/entities/repository/api/get-branch-repositories-from-api");

type ApiResult = Awaited<ReturnType<typeof getBranchRepositoriesFromApi>>;

const node = (overrides: Record<string, unknown> = {}) => ({
  id: "repo-1",
  __typename: "CoreRepository",
  display_label: "infrastructure-templates (label)",
  name: { value: "infrastructure-templates" },
  commit: { value: "8f3c2a1" },
  sync_status: {
    value: "in-sync",
    label: "In Sync",
    color: "#60a5fa",
    description: "The repository is syncing correctly",
  },
  operational_status: { value: "online", label: "Online", color: "#86efac" },
  ...overrides,
});

function mockNodes(nodes: ReturnType<typeof node>[], count = nodes.length) {
  vi.mocked(getBranchRepositoriesFromApi).mockResolvedValue({
    data: { count, edges: nodes.map((n) => ({ node: n })) },
  } as unknown as ApiResult);
}

function mockErrors(errors: Array<{ message: string; extensions?: unknown }>) {
  vi.mocked(getBranchRepositoriesFromApi).mockResolvedValue({
    data: undefined,
    errors,
  } as unknown as ApiResult);
}

describe("getBranchRepositories", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps nodes to branch repositories", async () => {
    mockNodes([node()]);

    const result = await getBranchRepositories({ branchName: "feature", syncWithGit: true });

    expect(result).toEqual({
      status: "ok",
      count: 1,
      isTruncated: false,
      repositories: [
        {
          id: "repo-1",
          kind: "CoreRepository",
          name: "infrastructure-templates",
          isReadOnly: false,
          commit: "8f3c2a1",
          syncStatus: {
            value: "in-sync",
            label: "In Sync",
            color: "#60a5fa",
            description: "The repository is syncing correctly",
          },
          operationalStatus: { value: "online", label: "Online" },
        },
      ],
    });
  });

  it("falls back to display_label, then id, for the name", async () => {
    mockNodes([
      node({ id: "a", name: { value: null } }),
      node({ id: "b", name: null, display_label: null }),
    ]);

    const result = await getBranchRepositories({ branchName: "feature", syncWithGit: true });

    expect(result.status === "ok" && result.repositories.map((r) => r.name)).toEqual([
      "infrastructure-templates (label)",
      "b",
    ]);
  });

  it("marks read-only repositories from __typename", async () => {
    mockNodes([node({ __typename: "CoreReadOnlyRepository" })]);

    const result = await getBranchRepositories({ branchName: "feature", syncWithGit: true });

    expect(result.status === "ok" && result.repositories[0]).toMatchObject({
      kind: "CoreReadOnlyRepository",
      isReadOnly: true,
    });
  });

  it("maps a missing commit and statuses to null", async () => {
    mockNodes([node({ commit: { value: null }, sync_status: null, operational_status: null })]);

    const result = await getBranchRepositories({ branchName: "feature", syncWithGit: true });

    expect(result.status === "ok" && result.repositories[0]).toMatchObject({
      commit: null,
      syncStatus: { value: null, label: null, color: null, description: null },
      operationalStatus: { value: null, label: null },
    });
  });

  it("queries every repository kind on the page's branch when Sync with Git is on", async () => {
    mockNodes([]);

    await getBranchRepositories({ branchName: "feature", syncWithGit: true });

    expect(getBranchRepositoriesFromApi).toHaveBeenCalledWith({
      branchName: "feature",
      kind: "CoreGenericRepository",
    });
  });

  it("queries only read-only repositories when Sync with Git is off", async () => {
    mockNodes([]);

    await getBranchRepositories({ branchName: "feature", syncWithGit: false });

    expect(getBranchRepositoriesFromApi).toHaveBeenCalledWith({
      branchName: "feature",
      kind: "CoreReadOnlyRepository",
    });
  });

  it("returns denied on a PERMISSION_DENIED error", async () => {
    mockErrors([
      {
        message: "You do not have one of the following permissions",
        extensions: { code: "PERMISSION_DENIED", http_status: 403, data: {} },
      },
    ]);

    const result = await getBranchRepositories({ branchName: "feature", syncWithGit: true });

    expect(result).toEqual({ status: "denied" });
  });

  it("throws on any other error", async () => {
    mockErrors([{ message: "Something broke", extensions: { code: "UNDEFINED_ERROR" } }]);

    await expect(
      getBranchRepositories({ branchName: "feature", syncWithGit: true })
    ).rejects.toThrow("Something broke");
  });

  it("throws with every message when a denial comes with another error", async () => {
    mockErrors([
      {
        message: "You do not have one of the following permissions",
        extensions: { code: "PERMISSION_DENIED", http_status: 403, data: {} },
      },
      { message: "Something broke", extensions: { code: "UNDEFINED_ERROR" } },
    ]);

    await expect(
      getBranchRepositories({ branchName: "feature", syncWithGit: true })
    ).rejects.toThrow("You do not have one of the following permissions; Something broke");
  });

  it("is truncated when the count exceeds the returned repositories", async () => {
    mockNodes([node()], 501);

    const result = await getBranchRepositories({ branchName: "feature", syncWithGit: true });

    expect(result).toMatchObject({ status: "ok", count: 501, isTruncated: true });
  });

  it("drops nodes without an id", async () => {
    mockNodes([node({ id: null }), node({ id: "repo-2" })]);

    const result = await getBranchRepositories({ branchName: "feature", syncWithGit: true });

    expect(result.status === "ok" && result.repositories.map((r) => r.id)).toEqual(["repo-2"]);
  });
});
