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

  it("requests the profiles field for a node schema with generate_profile enabled", async () => {
    // GIVEN
    const schema = generateNodeSchema({ generate_profile: true }) as NodeSchema;

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

  it("does not request the profiles field for a generic schema even when generate_profile is enabled", async () => {
    // GIVEN
    const schema = generateGenericSchema({ generate_profile: true }) as unknown as GenericSchema;

    // WHEN
    await getObjectForEditingFromApi({
      // A generic kind can be reached via its route (e.g. CoreGenericRepository),
      // but generics have no `profiles` GraphQL field.
      schema: schema as unknown as NodeSchema,
      objectId: "object-id",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(getRequestedQueryString()).not.toContain("profiles");
  });
});
