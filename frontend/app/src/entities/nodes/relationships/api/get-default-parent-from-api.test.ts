import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

import { getDefaultParentFromApi } from "./get-default-parent-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// the query. Keep that real and stub only the transport.
vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

vi.mock("@/entities/schema/domain/use-cases/get-schema", () => ({
  getSchema: vi.fn(),
}));

describe("getDefaultParentFromApi", () => {
  const parentRelationship = {
    peer: "TestDevice",
    direction: "inbound" as const,
    identifier: "device__interface",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Schema exposing the child relationship used to derive the parent filter attribute.
    vi.mocked(getSchema).mockReturnValue({
      schema: {
        relationships: [
          { name: "interfaces", direction: "outbound", identifier: "device__interface" },
        ],
      },
    } as any);
    vi.mocked(graphqlClient.query).mockResolvedValue({ data: {} } as any);
  });

  it("does not query (no auto-selected parent) when there is no current relationship value", async () => {
    const result = await getDefaultParentFromApi({
      parentRelationship,
      defaultValue: undefined,
      branchName: "main",
      atDate: null,
    });

    expect(graphqlClient.query).not.toHaveBeenCalled();
    expect(result).toEqual({ data: null, error: null });
  });

  it("queries filtered by the current value id when a relationship value exists", async () => {
    await getDefaultParentFromApi({
      parentRelationship,
      defaultValue: {
        source: { type: "user" },
        value: { id: "interface-1", __typename: "TestInterface", display_label: "eth0" },
      },
      branchName: "main",
      atDate: null,
    });

    expect(graphqlClient.query).toHaveBeenCalledTimes(1);
    expect(vi.mocked(graphqlClient.query).mock.calls[0]![0].variables).toEqual({
      ids: ["interface-1"],
    });
  });
});
