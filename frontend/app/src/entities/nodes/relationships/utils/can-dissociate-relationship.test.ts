import { generateNodeSchema, generateRelationshipSchema } from "../../../../../tests/fake/schema";
import { canDissociateRelationship } from "./can-dissociate-relationship";

describe("Dissociate action", () => {
  it("should be enabled from relationship schema", () => {
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          name: "relationshipName",
          peer: "TestPeer",
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
        }),
      ],
    });

    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "relationshipName",
      parentSchema,
      peerSchema,
      relationshipsCount: 0,
    });

    expect(isDissociateAllowed).to.eq(true);
  });

  it("should be enabled from peers min count", () => {
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          name: "relationshipName",
          peer: "TestPeer",
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          optional: false,
          peer: "TestNode",
          min_count: 2,
        }),
      ],
    });

    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "relationshipName",
      parentSchema,
      peerSchema,
      relationshipsCount: 3,
    });

    expect(isDissociateAllowed).to.eq(true);
  });

  it("should be enabled from peers global count", () => {
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          name: "relationshipName",
          peer: "TestPeer",
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          optional: false,
          peer: "TestNode",
        }),
      ],
    });

    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "relationshipName",
      parentSchema,
      peerSchema,
      relationshipsCount: 3,
    });
    expect(isDissociateAllowed).to.eq(true);
  });

  it("should be disabled from relationship schema", () => {
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          name: "relationshipName",
          peer: "TestPeer",
          optional: false,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          optional: false,
          peer: "TestNode",
        }),
      ],
    });

    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "relationshipName",
      parentSchema,
      peerSchema,
      relationshipsCount: 0,
    });
    expect(isDissociateAllowed).to.eq(false);
  });

  it("should be disabled from peers min count", () => {
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          name: "relationshipName",
          peer: "TestPeer",
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
          cardinality: "many",
          optional: false,
          peer: "TestNode",
        }),
      ],
    });

    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "relationshipName",
      parentSchema,
      peerSchema,
      relationshipsCount: 2,
    });
    expect(isDissociateAllowed).to.eq(false);
  });

  it("should be disabled from peers global count", () => {
    const parentSchema = generateNodeSchema({
      kind: "Test",
      name: "Node",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          name: "relationshipName",
          peer: "TestPeer",
          optional: false,
        }),
      ],
    });

    const peerSchema = generateNodeSchema({
      kind: "Test",
      name: "Peer",
      relationships: [
        generateRelationshipSchema({
          cardinality: "many",
          optional: false,
          peer: "TestNode",
        }),
      ],
    });

    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "relationshipName",
      parentSchema,
      peerSchema,
      relationshipsCount: 0,
    });
    expect(isDissociateAllowed).to.eq(false);
  });
});
