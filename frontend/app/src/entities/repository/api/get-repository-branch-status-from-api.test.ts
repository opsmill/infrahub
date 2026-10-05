import { print } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getRepositoryBranchStatusFromApi } from "./get-repository-branch-status-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// the query. Keep that real and stub only the transport.
vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

const queryMock = vi.mocked(graphqlClient.query);

const sentRequest = () => {
  const [request] = queryMock.mock.calls.at(0) ?? [];
  if (!request) throw new Error("no request was sent");
  return request;
};

const sentQuery = () => print(sentRequest().query as never);

// The card narrows on a branch's own fields only. These three reach the repository's attributes
// instead, and the resolver applies them, so declaring one would quietly change the rows returned.
const UNDECLARED_ARGUMENTS = ["sync_status__value", "internal_status__value", "own_values_only"];

describe("getRepositoryBranchStatusFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryMock.mockResolvedValue({
      data: { InfrahubRepositoryBranchStatus: { count: 0, edges: [] } },
    } as never);
  });

  it.each(UNDECLARED_ARGUMENTS)("declares no %s variable", async (argument) => {
    // WHEN
    await getRepositoryBranchStatusFromApi({ branchName: "main", id: "repository-1" });

    // THEN not declaring it is the whole of the guarantee: a variable the document never names
    // cannot be sent whatever a caller passes
    expect(sentQuery()).not.toContain(argument);
  });

  it("asks for no node metadata, so no timestamp can be rendered", async () => {
    // WHEN
    await getRepositoryBranchStatusFromApi({ branchName: "main", id: "repository-1" });

    // THEN ordering by a timestamp must not pull one into the selection set
    expect(sentQuery()).not.toContain("node_metadata");
  });

  it("carries the branch to the transport", async () => {
    // WHEN
    await getRepositoryBranchStatusFromApi({ branchName: "feature-auth", id: "repository-1" });

    // THEN
    expect(sentRequest().context).toMatchObject({ branch: "feature-auth" });
  });
});
