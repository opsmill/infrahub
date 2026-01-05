import { describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { generateNodeSchema, generateRelationshipSchema } from "../../../../../tests/fake/schema";
import { canDissociateRelationship } from "./can-dissociate-relationship";

describe("canDissociateRelationship", () => {
  it("should return false if relationship not found in parent schema", () => {
    // GIVEN
    const parentSchema = generateNodeSchema();

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "nonexistent",
      parentSchema,
      relationshipsCount: 1,
    });

    // THEN
    expect(result).toBe(false);
  });

  it("should handle missing peer schema", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "rel",
          peer: "NonexistentPeer",
          direction: "bidirectional",
          optional: true,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "rel",
      parentSchema,
      relationshipsCount: 1,
    });

    // THEN
    expect(result).toBe(true);
  });

  it("should allow dissociation when both sides are optional bidirectional", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "optional_rel",
          peer: "TestPeer",
          direction: "bidirectional",
          optional: true,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "TestPeer",
      relationships: [
        generateRelationshipSchema({
          name: "peer_rel",
          peer: "TestParent",
          direction: "bidirectional",
          optional: true,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "optional_rel",
      parentSchema,
      relationshipsCount: 1,
    });

    // THEN
    expect(result).toBe(true);
  });

  it("should not allow dissociation when below min count for required relationship", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "required_rel",
          peer: "TestPeer",
          direction: "bidirectional",
          optional: false,
          min_count: 1,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "TestPeer",
      relationships: [
        generateRelationshipSchema({
          name: "peer_rel",
          peer: "TestParent",
          direction: "bidirectional",
          optional: true,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "required_rel",
      parentSchema,
      relationshipsCount: 1,
    });

    // THEN
    expect(result).toBe(false);
  });

  it("should allow dissociation when above min count", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "required_rel",
          peer: "TestPeer",
          direction: "bidirectional",
          optional: false,
          min_count: 1,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "TestPeer",
      relationships: [
        generateRelationshipSchema({
          name: "peer_rel",
          peer: "TestParent",
          direction: "bidirectional",
          optional: true,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "required_rel",
      parentSchema,
      relationshipsCount: 2,
    });

    // THEN
    expect(result).toBe(true);
  });

  it("should handle inbound directional relationships correctly", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "inbound_rel",
          peer: "TestPeer",
          direction: "inbound",
          optional: true,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "TestPeer",
      relationships: [
        generateRelationshipSchema({
          name: "outbound_rel",
          peer: "TestParent",
          direction: "outbound",
          optional: true,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "inbound_rel",
      parentSchema,
      relationshipsCount: 1,
    });

    // THEN
    expect(result).toBe(true);
  });

  it("should handle outbound directional relationships correctly", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "outbound_rel",
          peer: "TestPeer",
          direction: "outbound",
          optional: false,
          min_count: 2,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "TestPeer",
      relationships: [
        generateRelationshipSchema({
          name: "inbound_rel",
          peer: "TestParent",
          direction: "inbound",
          optional: true,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "outbound_rel",
      parentSchema,
      relationshipsCount: 3,
    });

    // THEN
    expect(result).toBe(true);
  });

  it("should not allow dissociation when parent and peer are required", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "required_rel",
          peer: "TestPeer",
          direction: "bidirectional",
          optional: false,
          min_count: 1,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "TestPeer",
      relationships: [
        generateRelationshipSchema({
          name: "peer_rel",
          peer: "TestParent",
          direction: "bidirectional",
          optional: false,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "required_rel",
      parentSchema,
      relationshipsCount: 1,
    });

    // THEN
    expect(result).toBe(false);
  });

  it("should not allow dissociation when parent is optional but peer is required", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "optional_rel",
          peer: "TestPeer",
          direction: "bidirectional",
          optional: true,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "TestPeer",
      relationships: [
        generateRelationshipSchema({
          name: "peer_rel",
          peer: "TestParent",
          direction: "bidirectional",
          optional: false,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "optional_rel",
      parentSchema,
      relationshipsCount: 1,
    });

    // THEN
    expect(result).toBe(false);
  });

  it("should handle undefined min_count correctly", () => {
    // GIVEN
    const parentSchema = generateNodeSchema({
      kind: "TestParent",
      relationships: [
        generateRelationshipSchema({
          name: "rel",
          peer: "TestPeer",
          direction: "bidirectional",
          optional: false,
          min_count: undefined,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "TestPeer",
      relationships: [
        generateRelationshipSchema({
          name: "peer_rel",
          peer: "TestParent",
          direction: "bidirectional",
          optional: true,
        }),
      ],
    });

    store.set(nodeSchemasAtom, [parentSchema, peerSchema]);

    // WHEN
    const result = canDissociateRelationship({
      relationshipName: "rel",
      parentSchema,
      relationshipsCount: 2,
    });

    // THEN
    expect(result).toBe(true);
  });
});
