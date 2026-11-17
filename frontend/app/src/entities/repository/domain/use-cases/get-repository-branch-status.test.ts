import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getRepositoryBranchStatusFromApi } from "@/entities/repository/api/get-repository-branch-status-from-api";
import { RepositoryBranchStatusError } from "@/entities/repository/domain/model/repository-branch-status";
import { getRepositoryBranchStatus } from "@/entities/repository/domain/use-cases/get-repository-branch-status";

import { generateRepositoryBranchStatusPayloadBefore } from "../../../../../tests/fake/repository";

vi.mock("@/entities/repository/api/get-repository-branch-status-from-api");

const PARAMS = { branchName: "main", id: "repo-1", limit: 20, offset: 0 };

function rejectWithExtensions(extensions: Record<string, unknown>) {
  const combinedError = new CombinedError({
    graphQLErrors: [new GraphQLError("nope", { extensions })],
  });

  vi.mocked(getRepositoryBranchStatusFromApi).mockRejectedValue(
    new Error("nope", { cause: combinedError })
  );
}

async function codeOf(promise: Promise<unknown>): Promise<string> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof RepositoryBranchStatusError) return error.code;
    throw error;
  }

  throw new Error("expected the use case to throw");
}

describe("getRepositoryBranchStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("forwards its parameters to the api boundary and maps the page", async () => {
    vi.mocked(getRepositoryBranchStatusFromApi).mockResolvedValue({
      data: { InfrahubRepositoryBranchStatus: generateRepositoryBranchStatusPayloadBefore() },
    });

    const page = await getRepositoryBranchStatus(PARAMS);

    expect(getRepositoryBranchStatusFromApi).toHaveBeenCalledWith(PARAMS);
    expect(page.rows.map((row) => row.name)).toEqual(["main", "feature-auth", "staging"]);
    expect(page.count).toBe(3);
  });

  it("maps a PERMISSION_DENIED payload to the PERMISSION_DENIED code", async () => {
    rejectWithExtensions({ code: "PERMISSION_DENIED", http_status: 403, data: {} });

    await expect(codeOf(getRepositoryBranchStatus(PARAMS))).resolves.toBe("PERMISSION_DENIED");
  });

  it("maps any other catalogue payload to the UNKNOWN code", async () => {
    rejectWithExtensions({ code: "NODE_NOT_FOUND", http_status: 404, data: {} });

    await expect(codeOf(getRepositoryBranchStatus(PARAMS))).resolves.toBe("UNKNOWN");
  });

  it("maps an unrecognised payload to the UNKNOWN code", async () => {
    rejectWithExtensions({ somethingElse: true });

    await expect(codeOf(getRepositoryBranchStatus(PARAMS))).resolves.toBe("UNKNOWN");
  });

  it("maps a network failure carrying no extensions to the UNKNOWN code", async () => {
    vi.mocked(getRepositoryBranchStatusFromApi).mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(codeOf(getRepositoryBranchStatus(PARAMS))).resolves.toBe("UNKNOWN");
  });

  it("keeps the original failure as the cause", async () => {
    const networkError = new TypeError("Failed to fetch");
    vi.mocked(getRepositoryBranchStatusFromApi).mockRejectedValue(networkError);

    await expect(getRepositoryBranchStatus(PARAMS)).rejects.toMatchObject({
      name: "RepositoryBranchStatusError",
      cause: networkError,
    });
  });
});
