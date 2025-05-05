import {
  deviceMockSchema,
  deviceRelationshipMinCountMockSchema,
  deviceRelationshipNotOptionalMockSchema,
} from "../../../../../tests/mocks/data/devices";
import {
  interfaceL2MockSchema,
  interfaceL2WithoutDeviceMockSchema,
} from "../../../../../tests/mocks/data/interfaces";
import { canDissociateRelationship } from "./can-dissociate-relationship";

describe("Dissociate action", () => {
  it("should be enabled from relationship schema", () => {
    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "interfaces",
      parentSchema: deviceMockSchema,
      peerSchema: interfaceL2WithoutDeviceMockSchema,
      relationshipsCount: 0,
    });
    expect(isDissociateAllowed).to.eq(true);
  });

  it("should be enabled from peers min count", () => {
    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "interfaces",
      parentSchema: deviceRelationshipMinCountMockSchema,
      peerSchema: interfaceL2WithoutDeviceMockSchema,
      relationshipsCount: 3,
    });
    expect(isDissociateAllowed).to.eq(true);
  });

  it("should be enabled from peers global count", () => {
    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "interfaces",
      parentSchema: deviceRelationshipNotOptionalMockSchema,
      peerSchema: interfaceL2WithoutDeviceMockSchema,
      relationshipsCount: 3,
    });
    expect(isDissociateAllowed).to.eq(true);
  });

  it("should be disabled from relationship schema", () => {
    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "interfaces",
      parentSchema: deviceMockSchema,
      peerSchema: interfaceL2MockSchema,
      relationshipsCount: 0,
    });
    expect(isDissociateAllowed).to.eq(false);
  });

  it("should be disabled from peers min count", () => {
    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "interfaces",
      parentSchema: deviceRelationshipMinCountMockSchema,
      peerSchema: interfaceL2MockSchema,
      relationshipsCount: 2,
    });
    expect(isDissociateAllowed).to.eq(false);
  });

  it("should be disabled from peers global count", () => {
    const isDissociateAllowed = canDissociateRelationship({
      relationshipName: "interfaces",
      parentSchema: deviceRelationshipNotOptionalMockSchema,
      peerSchema: interfaceL2MockSchema,
      relationshipsCount: 0,
    });
    expect(isDissociateAllowed).to.eq(false);
  });
});
