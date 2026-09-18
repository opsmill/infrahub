import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getRelationshipsFromApi } from "./get-relationships-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// the query. Stub it with the identity so the assertions can read the generated query string.
vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { query: vi.fn() },
}));

const lastCall = () => vi.mocked(graphqlClient.query).mock.calls[0]![0];
const generatedQuery = () => lastCall().query as unknown as string;
const sentVariables = () => lastCall().variables as Record<string, unknown>;

describe("getRelationshipsFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(graphqlClient.query).mockResolvedValue({ data: {} } as any);
  });

  it("declares pagination and search as variables instead of inlining them", async () => {
    // WHEN
    await getRelationshipsFromApi({
      peer: "BuiltinTag",
      limit: 10,
      offset: 20,
      search: "blue",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(generatedQuery()).toContain("$limit: Int");
    expect(generatedQuery()).toContain("$offset: Int");
    expect(generatedQuery()).toContain("$search: String");
    expect(generatedQuery()).not.toContain("limit: 10");
    expect(generatedQuery()).not.toContain("offset: 20");
    expect(generatedQuery()).not.toContain('any__value: "blue"');
    expect(sentVariables()).toMatchObject({ limit: 10, offset: 20, search: "blue" });
  });

  it("builds one document for every page, so the backend can reuse its parsed query", async () => {
    // GIVEN
    await getRelationshipsFromApi({
      peer: "BuiltinTag",
      limit: 10,
      offset: 0,
      branchName: "main",
      atDate: null,
    });
    const firstPage = generatedQuery();

    // WHEN
    vi.mocked(graphqlClient.query).mockClear();
    await getRelationshipsFromApi({
      peer: "BuiltinTag",
      limit: 10,
      offset: 10,
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(generatedQuery()).toBe(firstPage);
  });

  it("declares id filters as variables and leaves other filters inlined", async () => {
    // WHEN
    await getRelationshipsFromApi({
      peer: "BuiltinTag",
      branchName: "main",
      atDate: null,
      filterQuery: { ids: ["tag-1"], parent__ids: ["parent-1"], name__value: "blue" },
    });

    // THEN
    expect(generatedQuery()).toContain("$ids: [ID]");
    expect(generatedQuery()).toContain("$parent__ids: [ID]");
    expect(generatedQuery()).toContain("ids: $ids");
    expect(generatedQuery()).toContain("parent__ids: $parent__ids");
    expect(sentVariables()).toMatchObject({ ids: ["tag-1"], parent__ids: ["parent-1"] });

    // Non-id filters have no GraphQL type mapping yet, so they stay inlined.
    expect(generatedQuery()).toContain('name__value: "blue"');
    expect(sentVariables()).not.toHaveProperty("name__value");
  });

  it("keeps sending the zero bounds when the caller omits pagination and search", async () => {
    // WHEN
    await getRelationshipsFromApi({
      peer: "BuiltinTag",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(sentVariables()).toMatchObject({ limit: 0, offset: 0, search: "" });
  });
});
