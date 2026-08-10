import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getObjectForEditingFromApi } from "@/entities/nodes/object/api/get-object-for-editing-from-api";
import type { NodeSchema } from "@/entities/schema/domain/model/schema";

import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

vi.mock("@/shared/api/graphql/client", () => ({
  graphql: vi.fn((queryString: string) => queryString),
  graphqlClient: {
    query: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

const profilesRelationship = generateRelationshipSchema({
  name: "profiles",
  peer: "CoreProfile",
  identifier: "node__profile",
});

const getRequestedQueryString = () => {
  const [callArgs] = vi.mocked(graphqlClient.query).mock.calls;
  const query = callArgs?.[0]?.query;
  return typeof query === "string" ? query : "";
};

describe("getObjectForEditingFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("requests the profiles field for a node exposing a profiles relationship", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      generate_profile: true,
      relationships: [profilesRelationship],
    });

    // WHEN
    await getObjectForEditingFromApi({
      schema,
      objectId: "object-id",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(getRequestedQueryString()).toContain("profiles");
    expect(getRequestedQueryString()).toContain("profile_priority");
  });

  it("does not request the profiles field for a generic without a profiles relationship", async () => {
    // GIVEN
    const schema = generateGenericSchema({
      generate_profile: true,
      relationships: [],
    }) as unknown as NodeSchema;

    // WHEN
    await getObjectForEditingFromApi({
      schema,
      objectId: "object-id",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(getRequestedQueryString()).not.toContain("profiles");
  });

  it("requests the profiles field for a generic exposing a profiles relationship", async () => {
    // GIVEN
    const schema = generateGenericSchema({
      generate_profile: true,
      relationships: [profilesRelationship],
    }) as unknown as NodeSchema;

    // WHEN
    await getObjectForEditingFromApi({
      schema,
      objectId: "object-id",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(getRequestedQueryString()).toContain("profiles");
    expect(getRequestedQueryString()).toContain("profile_priority");
  });
});
