import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import type { NodeSchema } from "@/entities/schema/domain/model/schema";

import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import { getObjectForEditingFromApi } from "./get-object-for-editing-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// the query. Stub it with the identity so the assertions can read the generated query string.
vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { query: vi.fn() },
}));

const profilesRelationship = generateRelationshipSchema({
  name: "profiles",
  peer: "CoreProfile",
  identifier: "node__profile",
});

const getGeneratedQuery = () =>
  vi.mocked(graphqlClient.query).mock.calls[0]![0].query as unknown as string;

describe("getObjectForEditingFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(graphqlClient.query).mockResolvedValue({ data: {} } as any);
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
    expect(getGeneratedQuery()).toContain("profiles");
    expect(getGeneratedQuery()).toContain("profile_priority");
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
    expect(getGeneratedQuery()).not.toContain("profiles");
  });

  it("requests the profiles field for a generic exposing a profiles relationship", async () => {
    // GIVEN
    const schema = generateGenericSchema({
      generate_profile: true,
      relationships: [
        generateRelationshipSchema({
          name: "used_by",
          peer: "CoreNode",
          identifier: "profile__node",
        }),
        profilesRelationship,
      ],
    }) as unknown as NodeSchema;

    // WHEN
    await getObjectForEditingFromApi({
      schema,
      objectId: "object-id",
      branchName: "main",
      atDate: null,
    });

    // THEN
    expect(getGeneratedQuery()).toContain("profiles");
    expect(getGeneratedQuery()).toContain("profile_priority");
  });
});
