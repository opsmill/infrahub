import { describe, expect, it } from "vitest";

import { generateObjectEditFormQuery } from "@/entities/nodes/object-item-edit/generateObjectEditFormQuery";
import type { NodeSchema } from "@/entities/schema/types";

import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../tests/fake/schema";

const profilesRelationship = generateRelationshipSchema({
  name: "profiles",
  peer: "CoreProfile",
  identifier: "node__profile",
});

describe("generateObjectEditFormQuery", () => {
  it("requests the profiles field for a node exposing a profiles relationship", () => {
    // GIVEN
    const schema = generateNodeSchema({
      generate_profile: true,
      relationships: [profilesRelationship],
    });

    // WHEN
    const query = generateObjectEditFormQuery({ schema, objectId: "object-id" });

    // THEN
    expect(query).toContain("profiles");
    expect(query).toContain("profile_priority");
  });

  it("does not request the profiles field for a generic without a profiles relationship", () => {
    // GIVEN
    const schema = generateGenericSchema({
      generate_profile: true,
      relationships: [],
    }) as unknown as NodeSchema;

    // WHEN
    const query = generateObjectEditFormQuery({ schema, objectId: "object-id" });

    // THEN
    expect(query).not.toContain("profiles");
  });

  it("requests the profiles field for a generic exposing a profiles relationship", () => {
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
    const query = generateObjectEditFormQuery({ schema, objectId: "object-id" });

    // THEN
    expect(query).toContain("profiles");
    expect(query).toContain("profile_priority");
  });
});
