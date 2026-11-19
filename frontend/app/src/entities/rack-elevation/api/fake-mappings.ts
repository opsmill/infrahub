import type { RackElevationMapping } from "@/entities/rack-elevation/domain/model/mapping";

export const FAKE_MAPPINGS: RackElevationMapping[] = [
  {
    id: "mapping-dcim",
    name: "Data center racks",
    rackKind: "DcimRack",
    rack: {
      label: { type: "path", path: ["name"] },
      height: { type: "path", path: ["rack_type", "u_count"] },
    },
    itemSources: [
      {
        id: "source-devices",
        name: "Devices",
        relationship: "devices",
        frontValues: "front",
        rearValues: "rear",
        fields: {
          label: { type: "path", path: ["name"] },
          subtitle: {
            type: "template",
            template: "{device_type.manufacturer} {device_type.model}",
          },
          position: { type: "path", path: ["position"] },
          height: { type: "path", path: ["device_type", "u_height"] },
          face: { type: "path", path: ["face"] },
          fullDepth: { type: "path", path: ["device_type", "is_full_depth"] },
          color: { type: "path", path: ["role", "color"] },
        },
      },
      {
        id: "source-patch-panels",
        name: "Patch panels",
        relationship: "patch_panels",
        frontValues: "front",
        rearValues: "back, rear",
        fields: {
          label: { type: "path", path: ["name"] },
          subtitle: { type: "template", template: "{port_count} ports" },
          position: { type: "path", path: ["rack_unit"] },
          height: { type: "path", path: ["size_u"] },
          face: { type: "path", path: ["mounted_side"] },
          fullDepth: { type: "constant", value: "false" },
          color: { type: "constant", value: "#a8a29e" },
        },
      },
      {
        id: "source-pdus",
        name: "Power distribution units",
        relationship: "pdus",
        frontValues: "front",
        rearValues: "rear",
        fields: {
          label: { type: "path", path: ["name"] },
          subtitle: { type: "template", template: "Phase {phase}" },
          position: { type: "path", path: ["position"] },
          height: { type: "path", path: ["height"] },
          face: { type: "path", path: ["face"] },
          fullDepth: { type: "constant", value: "false" },
          color: { type: "constant", value: "#eab308" },
        },
      },
    ],
  },
  {
    id: "mapping-compute",
    name: "Compute racks",
    rackKind: "LocationRack",
    rack: {
      label: { type: "template", template: "{name} ({facility_id})" },
      height: { type: "path", path: ["height"] },
    },
    itemSources: [
      {
        id: "source-servers",
        name: "Servers",
        relationship: "servers",
        frontValues: "front",
        rearValues: "rear",
        fields: {
          label: { type: "path", path: ["asset_tag"] },
          subtitle: { type: "template", template: "{hostname} · {model.vendor} {model}" },
          position: { type: "path", path: ["rack_slot"] },
          height: { type: "path", path: ["model", "units"] },
          face: { type: "path", path: ["mount_side"] },
          fullDepth: { type: "path", path: ["model", "full_depth"] },
          color: { type: "path", path: ["tenant", "color"] },
        },
      },
    ],
  },
];
