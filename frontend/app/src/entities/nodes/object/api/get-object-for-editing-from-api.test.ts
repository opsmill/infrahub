import { beforeEach, describe, expect, it, vi } from "vitest";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { getObjectForEditingFromApi } from "@/entities/nodes/object/api/get-object-for-editing-from-api";
import type { GenericSchema, NodeSchema } from "@/entities/schema/domain/model/schema";

import { generateGenericSchema, generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/shared/api/graphql/graphqlClientApollo", () => ({
  default: {
    query: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

const getRequestedQueryString = () => {
  const [callArgs] = vi.mocked(graphqlClient.query).mock.calls;
  return callArgs?.[0]?.query?.loc?.source.body ?? "";
};

describe("getObjectForEditingFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("requests the profiles field for a node schema that exposes a profiles relationship", async () => {
    // GIVEN a profile-enabled node whose schema carries a `profiles` relationship
    const schema = generateNodeSchema() as NodeSchema;

    // WHEN
    await getObjectForEditingFromApi({
      schema,
      objectId: "object-id",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(getRequestedQueryString()).toContain("profiles");
  });

  it("does not request the profiles field for a generic without a profiles relationship", async () => {
    // GIVEN a Core-style generic (e.g. CoreGenericRepository): it lives in a restricted
    // namespace, so the backend never adds a `profiles` relationship and GraphQL exposes no
    // `profiles` field for it.
    const schema = generateGenericSchema({
      generate_profile: true,
      relationships: [],
    }) as unknown as GenericSchema;

    // WHEN the generic kind is reached via its route
    await getObjectForEditingFromApi({
      schema: schema as unknown as NodeSchema,
      objectId: "object-id",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(getRequestedQueryString()).not.toContain("profiles");
  });

  it("requests the profiles field for a generic that exposes a profiles relationship", async () => {
    // GIVEN a Builtin-IP-style generic (e.g. BuiltinIPAddress): it is `used_by` concrete kinds
    // AND, because its namespace is not restricted for profiles, the backend adds a `profiles`
    // relationship so the GraphQL type does expose the `profiles` field. The previous
    // `!isGenericSchema(...)` guard wrongly stripped `profiles` for this case.
    const schema = generateGenericSchema() as unknown as GenericSchema;
    expect(schema.relationships?.some((rel) => rel.name === "profiles")).toBe(true);
    expect(schema.used_by?.length ?? 0).toBeGreaterThan(0);

    // WHEN
    await getObjectForEditingFromApi({
      schema: schema as unknown as NodeSchema,
      objectId: "object-id",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(getRequestedQueryString()).toContain("profiles");
  });
});
