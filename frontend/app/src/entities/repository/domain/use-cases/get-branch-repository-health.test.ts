import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getBranchRepositoryHealthFromApi } from "@/entities/repository/api/get-branch-repository-health-from-api";
import { BranchRepositoriesError } from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositoryHealth } from "@/entities/repository/domain/use-cases/get-branch-repository-health";

vi.mock("@/entities/repository/api/get-branch-repository-health-from-api");

type HealthResult = Awaited<ReturnType<typeof getBranchRepositoryHealthFromApi>>;

const node = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  __typename: "CoreRepository",
  display_label: id,
  name: { value: id },
  commit: { value: "8f3c2a1" },
  sync_status: { value: "in-sync", label: "In Sync", color: "#60a5fa", description: null },
  operational_status: { value: "online", label: "Online", color: "#86efac" },
  ...overrides,
});

const connection = (nodes: ReturnType<typeof node>[], count = nodes.length) => ({
  count,
  edges: nodes.map((n) => ({ node: n })),
});

const params = { branchName: "feature", syncWithGit: true, limit: 50 };

describe("getBranchRepositoryHealth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("asks the server for failed imports, unreachable and syncing repositories", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoryHealthFromApi).mockResolvedValue({
      importErrors: connection([]),
      unreachable: connection([]),
      syncing: { count: 0 },
    } as unknown as HealthResult);

    // WHEN
    await getBranchRepositoryHealth(params);

    // THEN
    expect(getBranchRepositoryHealthFromApi).toHaveBeenCalledWith({
      branchName: "feature",
      kind: "CoreGenericRepository",
      importErrorStatuses: ["error-import"],
      unreachableStatuses: ["error-cred", "error-connection", "error"],
      syncingStatuses: ["syncing"],
      limit: 50,
    });
  });

  it("only looks at read-only repositories when Sync with Git is off", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoryHealthFromApi).mockResolvedValue({
      importErrors: connection([]),
      unreachable: connection([]),
      syncing: { count: 0 },
    } as unknown as HealthResult);

    // WHEN
    await getBranchRepositoryHealth({ ...params, syncWithGit: false });

    // THEN
    expect(getBranchRepositoryHealthFromApi).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "CoreReadOnlyRepository" })
    );
  });

  it("maps both failing lists and the syncing count", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoryHealthFromApi).mockResolvedValue({
      importErrors: connection([node("broken", { sync_status: { value: "error-import" } })]),
      unreachable: connection([node("offline", { operational_status: { value: "error" } })]),
      syncing: { count: 3 },
    } as unknown as HealthResult);

    // WHEN
    const health = await getBranchRepositoryHealth(params);

    // THEN
    expect(health.importErrors.map(({ id }) => id)).toEqual(["broken"]);
    expect(health.unreachable.map(({ id }) => id)).toEqual(["offline"]);
    expect(health.syncingCount).toBe(3);
  });

  it("keeps the server's total of each failing list next to its capped rows", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoryHealthFromApi).mockResolvedValue({
      importErrors: connection([node("broken", { sync_status: { value: "error-import" } })], 120),
      unreachable: connection([node("offline", { operational_status: { value: "error" } })], 2),
      syncing: { count: 0 },
    } as unknown as HealthResult);

    // WHEN
    const health = await getBranchRepositoryHealth(params);

    // THEN
    expect(health.importErrorCount).toBe(120);
    expect(health.unreachableCount).toBe(2);
  });

  it("rejects with PERMISSION_DENIED when the user can't view repositories", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoryHealthFromApi).mockRejectedValue(
      new Error("Denied", {
        cause: new CombinedError({
          graphQLErrors: [
            new GraphQLError("Denied", { extensions: { code: "PERMISSION_DENIED" } }),
          ],
        }),
      })
    );

    // WHEN
    const error = await getBranchRepositoryHealth(params).catch((caught: unknown) => caught);

    // THEN
    expect(error).toBeInstanceOf(BranchRepositoriesError);
    expect(error).toMatchObject({ code: "PERMISSION_DENIED" });
  });
});
