import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { getObjectRelationshipsFromApi } from "./get-object-relationships-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// the query. Stub it with the identity so the assertions can read the generated query string.
vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { query: vi.fn() },
}));

const lastCall = () => vi.mocked(graphqlClient.query).mock.calls[0]![0];
const generatedQuery = () => lastCall().query as unknown as string;
const sentVariables = () => lastCall().variables as Record<string, unknown>;

const callWith = (overrides: { limit?: number; offset?: number }) =>
  getObjectRelationshipsFromApi({
    parentKind: "BuiltinTag",
    parentId: "parent-id",
    relationshipName: "member_of_groups",
    relationshipSchema: generateNodeSchema(),
    branchName: "main",
    atDate: null,
    ...overrides,
  });

describe("getObjectRelationshipsFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(graphqlClient.query).mockResolvedValue({ data: {} } as any);
  });

  it("declares the parent id and pagination as variables instead of inlining them", async () => {
    // WHEN
    await callWith({ limit: 10, offset: 20 });

    // THEN
    expect(generatedQuery()).toContain("$parentIds: [ID]");
    expect(generatedQuery()).toContain("$limit: Int");
    expect(generatedQuery()).toContain("$offset: Int");
    expect(generatedQuery()).toContain("ids: $parentIds");
    expect(generatedQuery()).toContain("limit: $limit");
    expect(generatedQuery()).toContain("offset: $offset");
    expect(generatedQuery()).not.toContain('ids: ["parent-id"]');
    expect(generatedQuery()).not.toContain("limit: 10");
    expect(generatedQuery()).not.toContain("offset: 20");
    expect(sentVariables()).toMatchObject({
      parentIds: ["parent-id"],
      limit: 10,
      offset: 20,
    });
  });

  it("keeps sending the zero bounds when the caller omits pagination", async () => {
    // WHEN
    await callWith({});

    // THEN
    expect(sentVariables()).toMatchObject({ limit: 0, offset: 0 });
  });
});
