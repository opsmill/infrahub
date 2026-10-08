import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getBranchRepositoriesFromApi } from "@/entities/repository/api/get-branch-repositories-from-api";
import { BranchRepositoriesError } from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositories } from "@/entities/repository/domain/use-cases/get-branch-repositories";

vi.mock("@/entities/repository/api/get-branch-repositories-from-api");

type PageResult = Awaited<ReturnType<typeof getBranchRepositoriesFromApi>>;

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

const permissionDenial = () =>
  new GraphQLError("You do not have one of the following permissions", {
    extensions: { code: "PERMISSION_DENIED", http_status: 403, data: {} },
  });

const thrownByTransport = (...graphQLErrors: GraphQLError[]) =>
  new Error(graphQLErrors[0]?.message, { cause: new CombinedError({ graphQLErrors }) });

const permissionDenied = () => thrownByTransport(permissionDenial(), permissionDenial());

describe("getBranchRepositories", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns the page's repositories and the server's total", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoriesFromApi).mockResolvedValue(
      connection([node("a"), node("b")], 42) as unknown as PageResult
    );

    // WHEN
    const result = await getBranchRepositories({
      branchName: "feature",
      syncWithGit: true,
      limit: 10,
      offset: 10,
    });

    // THEN
    expect(result.count).toBe(42);
    expect(result.repositories.map(({ id }) => id)).toEqual(["a", "b"]);
  });

  it.each([
    [true, "CoreGenericRepository"],
    [false, "CoreReadOnlyRepository"],
  ])(
    "with Sync with Git %s, asks for the %s page on the page's branch",
    async (syncWithGit, kind) => {
      // GIVEN
      vi.mocked(getBranchRepositoriesFromApi).mockResolvedValue(
        connection([]) as unknown as PageResult
      );

      // WHEN
      await getBranchRepositories({ branchName: "feature", syncWithGit, limit: 10, offset: 20 });

      // THEN
      expect(getBranchRepositoriesFromApi).toHaveBeenCalledWith({
        branchName: "feature",
        kind,
        limit: 10,
        offset: 20,
      });
    }
  );

  it("rejects with PERMISSION_DENIED when the user can't view repositories", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoriesFromApi).mockRejectedValue(permissionDenied());

    // WHEN
    const error = await getBranchRepositories({
      branchName: "feature",
      syncWithGit: true,
      limit: 10,
      offset: 0,
    }).catch((caught: unknown) => caught);

    // THEN
    expect(error).toBeInstanceOf(BranchRepositoriesError);
    expect(error).toMatchObject({ code: "PERMISSION_DENIED" });
  });

  it("rejects with UNKNOWN when a permission denial comes with another error", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoriesFromApi).mockRejectedValue(
      thrownByTransport(permissionDenial(), new GraphQLError("Database unavailable"))
    );

    // WHEN
    const error = await getBranchRepositories({
      branchName: "feature",
      syncWithGit: true,
      limit: 10,
      offset: 0,
    }).catch((caught: unknown) => caught);

    // THEN
    expect(error).toMatchObject({ code: "UNKNOWN" });
  });

  it("rejects with UNKNOWN on any other error, keeping its message", async () => {
    // GIVEN
    vi.mocked(getBranchRepositoriesFromApi).mockRejectedValue(new Error("Something broke"));

    // WHEN
    const error = await getBranchRepositories({
      branchName: "feature",
      syncWithGit: true,
      limit: 10,
      offset: 0,
    }).catch((caught: unknown) => caught);

    // THEN
    expect(error).toBeInstanceOf(BranchRepositoriesError);
    expect(error).toMatchObject({ code: "UNKNOWN", message: "Something broke" });
  });
});
