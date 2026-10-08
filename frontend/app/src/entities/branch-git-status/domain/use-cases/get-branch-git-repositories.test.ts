import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getBranchGitRepositoriesFromApi } from "@/entities/branch-git-status/api/get-branch-git-repositories-from-api";
import { getBranchGitRepositories } from "@/entities/branch-git-status/domain/use-cases/get-branch-git-repositories";

vi.mock("@/entities/branch-git-status/api/get-branch-git-repositories-from-api");

const PARAMS = { limit: 500, offset: 0 };

describe("getBranchGitRepositories", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("forwards its parameters to the api boundary and maps the page", async () => {
    // GIVEN
    vi.mocked(getBranchGitRepositoriesFromApi).mockResolvedValue({
      count: 1,
      edges: [{ node: { id: "r1", __typename: "CoreRepository", name: { value: "configs" } } }],
    });

    // WHEN
    const page = await getBranchGitRepositories(PARAMS);

    // THEN
    expect(getBranchGitRepositoriesFromApi).toHaveBeenCalledWith(PARAMS);
    expect(page).toEqual({
      repositories: [{ id: "r1", name: "configs", kind: "CoreRepository", isReadOnly: false }],
      count: 1,
    });
  });

  it("rejects with a PERMISSION_DENIED error when the list is denied", async () => {
    // GIVEN
    vi.mocked(getBranchGitRepositoriesFromApi).mockRejectedValue(
      new Error("denied", {
        cause: new CombinedError({
          graphQLErrors: [
            new GraphQLError("denied", {
              extensions: { code: "PERMISSION_DENIED", http_status: 403 },
            }),
          ],
        }),
      })
    );

    // WHEN
    const result = getBranchGitRepositories(PARAMS);

    // THEN
    await expect(result).rejects.toMatchObject({
      name: "BranchGitStatusError",
      code: "PERMISSION_DENIED",
    });
  });
});
