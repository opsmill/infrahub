import { describe, expect, it } from "vitest";
import { generateNodeSchema, generateRelationshipSchema } from "../../../../../tests/fake/schema";
import { canDissociateRelationship } from "./can-dissociate-relationship";

describe("canDissociateRelationship", () => {
  it("should return false when relationship not found in parent schema", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [],
    });
    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [],
    });

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "nonexistent",
      parentSchema,
      peerSchema,
      relationshipsCount: 0,
    });

    // THEN
    expect(result).toBe(false);
  });

  it("should return true when both relationships are optional", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Peer",
          optional: true,
        }),
      ],
    });
    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Node",
          optional: true,
        }),
      ],
    });

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 0,
    });

    // THEN
    expect(result).toBe(true);
  });

  it("should handle when peer relationship is a generic", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      inherit_from: ["BasePeer"],
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Peer",
          optional: false,
        }),
      ],
    });
    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "BasePeer",
          optional: true,
        }),
      ],
    });

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 2,
    });

    // THEN
    expect(result).toBe(true);
  });

  it("should handle when there is no relationship peer to parent", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Peer",
          optional: false,
          min_count: 2,
        }),
      ],
    });
    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [],
    });

    // WHEN
    const resultWithCountTooSmall = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 1,
    });
    const resultWithBiggerCount = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 3,
    });

    // THEN
    expect(resultWithCountTooSmall).toBe(false);
    expect(resultWithBiggerCount).toBe(true);
  });

  it("should respect min_count when relationship is required", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Peer",
          optional: false,
          min_count: 2,
        }),
      ],
    });
    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Node",
          optional: true,
        }),
      ],
    });
    // WHEN
    const resultWithCountSmaller = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 1,
    });
    const resultWithCountEqualToMinCount = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 2,
    });
    const resultWithCountBigger = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 3,
    });

    // THEN
    expect(resultWithCountSmaller).toBe(false);
    expect(resultWithCountEqualToMinCount).toBe(false);
    expect(resultWithCountBigger).toBe(true);
  });

  it("should handle when min_count is 0 and relationship is required", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Peer",
          optional: false,
          min_count: 0,
        }),
      ],
    });
    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [],
    });

    // WHEN
    const resultWithCount0 = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 0,
    });
    const resultWithCount1 = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 1,
    });
    const resultWithCount2 = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 2,
    });

    // THEN
    expect(resultWithCount0).toBe(false);
    expect(resultWithCount1).toBe(false);
    expect(resultWithCount2).toBe(true);
  });

  it("should handle different relationship directions", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Peer",
          direction: "outbound",
          optional: false,
          min_count: 1,
        }),
      ],
    });
    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          name: "test",
          peer: "Node",
          direction: "inbound",
          optional: true,
        }),
      ],
    });

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "test",
      parentSchema,
      peerSchema,
      relationshipsCount: 1,
    });

    // THEN
    expect(result).toEqual(false);
  });
});
