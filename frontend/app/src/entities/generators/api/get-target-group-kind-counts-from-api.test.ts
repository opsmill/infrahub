import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getTargetGroupKindCountsFromApi } from "./get-target-group-kind-counts-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// the query. Stub it with the identity so the assertions can read the generated query string.
vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { query: vi.fn() },
}));

const lastCall = () => vi.mocked(graphqlClient.query).mock.calls[0]![0];
const generatedQuery = () => lastCall().query as unknown as string;
const sentVariables = () => lastCall().variables as Record<string, unknown>;

describe("getTargetGroupKindCountsFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(graphqlClient.query).mockResolvedValue({ data: {} } as any);
  });

  it("declares each target group id as a variable instead of inlining it", async () => {
    // WHEN
    await getTargetGroupKindCountsFromApi({
      nodeKind: "InfraDevice",
      groupIds: ["group-a", "group-b"],
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(generatedQuery()).toContain("$group0Ids: [ID]");
    expect(generatedQuery()).toContain("$group1Ids: [ID]");
    expect(generatedQuery()).toContain("group0: InfraDevice (member_of_groups__ids: $group0Ids)");
    expect(generatedQuery()).toContain("group1: InfraDevice (member_of_groups__ids: $group1Ids)");
    expect(generatedQuery()).not.toContain("group-a");
    expect(generatedQuery()).not.toContain("group-b");
    expect(sentVariables()).toEqual({ group0Ids: ["group-a"], group1Ids: ["group-b"] });
  });
});
