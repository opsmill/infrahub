import {
  type RackElevation,
  type RackElevationItem,
  type RackElevationKind,
  RackElevationRole,
  RackFace,
  RackItemPlacement,
} from "../../src/entities/rack-elevation/domain/model/rack-elevation";

export const RACK_ID = "rack-r1";
export const LEAF_COLOR = "#4d90fe";
export const SERVER_COLOR = "#00d25b";
export const PDU_COLOR = "#ff9800";

export const generateRackElevationItem = (
  overrides: Partial<RackElevationItem> & Pick<RackElevationItem, "display_label">
): RackElevationItem => ({
  id: `item-${overrides.display_label}`,
  kind: "DcimDevice",
  label: overrides.display_label,
  color: null,
  placement: RackItemPlacement.MOUNTED,
  position: null,
  face: null,
  u_height: 1,
  full_depth: true,
  weight: null,
  type_id: null,
  type_display_label: null,
  ...overrides,
});

const switchType = { type_id: "type-switch", type_display_label: "Switch 1U" };

export const generateRackR1Elevation = (): RackElevation => ({
  rack: {
    id: RACK_ID,
    kind: "LocationRack",
    display_label: "R1",
    u_height: 12,
    used_units: 5,
    utilization: 41,
    total_weight: 57,
  },
  items: [
    generateRackElevationItem({
      display_label: "leaf1",
      color: LEAF_COLOR,
      position: 12,
      face: RackFace.FRONT,
      weight: 8,
      ...switchType,
    }),
    generateRackElevationItem({
      display_label: "leaf2",
      color: LEAF_COLOR,
      position: 11,
      face: RackFace.FRONT,
      weight: 8,
      ...switchType,
    }),
    generateRackElevationItem({
      display_label: "pp1",
      kind: "DcimRackAccessory",
      position: 10,
      face: RackFace.REAR,
      full_depth: false,
      weight: 2,
      type_id: "type-patch-panel",
      type_display_label: "Patch panel 1U",
    }),
    generateRackElevationItem({
      display_label: "blank1",
      kind: "DcimRackAccessory",
      position: 10,
      face: RackFace.FRONT,
      full_depth: false,
      weight: 1,
      type_id: "type-blanking-panel",
      type_display_label: "Blanking panel 1U",
    }),
    generateRackElevationItem({
      display_label: "srv1",
      color: SERVER_COLOR,
      position: 1,
      face: RackFace.FRONT,
      u_height: 2,
      weight: 25,
      type_id: "type-server",
      type_display_label: "Server 2U",
    }),
    generateRackElevationItem({
      display_label: "spare1",
      color: LEAF_COLOR,
      placement: RackItemPlacement.UNPOSITIONED,
      weight: 8,
      ...switchType,
    }),
    generateRackElevationItem({
      display_label: "pdu1",
      color: PDU_COLOR,
      placement: RackItemPlacement.ZERO_U,
      u_height: 0,
      full_depth: false,
      weight: 5,
      type_id: "type-pdu",
      type_display_label: "Vertical PDU",
    }),
  ],
});

export const generateRackElevationKinds = (): RackElevationKind[] => [
  { kind: "LocationRack", role: RackElevationRole.RACK },
  { kind: "DcimDevice", role: RackElevationRole.MOUNTABLE },
  { kind: "DcimRackAccessory", role: RackElevationRole.MOUNTABLE },
  { kind: "DcimDeviceType", role: RackElevationRole.MOUNTABLE_TYPE },
];
