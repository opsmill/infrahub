import type { SchemaKind } from "@/entities/rack-elevation/domain/model/schema";

const STATUS = ["active", "planned", "maintenance", "retired"];

const KINDS: SchemaKind[] = [
  {
    kind: "LocationSite",
    label: "Site",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "city", label: "City", kind: "Text" },
    ],
    relationships: [
      { name: "racks", label: "Racks", peer: "DcimRack", cardinality: "many" },
      {
        name: "location_racks",
        label: "Location racks",
        peer: "LocationRack",
        cardinality: "many",
      },
    ],
  },
  {
    kind: "DcimRack",
    label: "Rack",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "serial_number", label: "Serial number", kind: "Text" },
      { name: "status", label: "Status", kind: "Dropdown", choices: STATUS },
    ],
    relationships: [
      { name: "site", label: "Site", peer: "LocationSite", cardinality: "one" },
      { name: "rack_type", label: "Rack type", peer: "DcimRackType", cardinality: "one" },
      { name: "devices", label: "Devices", peer: "DcimDevice", cardinality: "many" },
      { name: "patch_panels", label: "Patch panels", peer: "DcimPatchPanel", cardinality: "many" },
      { name: "pdus", label: "Power distribution units", peer: "DcimPdu", cardinality: "many" },
    ],
  },
  {
    kind: "DcimRackType",
    label: "Rack type",
    displayAttribute: "model",
    attributes: [
      { name: "model", label: "Model", kind: "Text" },
      { name: "u_count", label: "Unit count", kind: "Number" },
      { name: "width", label: "Width", kind: "Text" },
    ],
    relationships: [{ name: "racks", label: "Racks", peer: "DcimRack", cardinality: "many" }],
  },
  {
    kind: "DcimDevice",
    label: "Device",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "position", label: "Position", kind: "Number" },
      { name: "face", label: "Face", kind: "Dropdown", choices: ["front", "rear"] },
      { name: "status", label: "Status", kind: "Dropdown", choices: STATUS },
      { name: "serial_number", label: "Serial number", kind: "Text" },
    ],
    relationships: [
      { name: "rack", label: "Rack", peer: "DcimRack", cardinality: "one" },
      { name: "device_type", label: "Device type", peer: "DcimDeviceType", cardinality: "one" },
      { name: "role", label: "Role", peer: "DcimDeviceRole", cardinality: "one" },
    ],
  },
  {
    kind: "DcimDeviceType",
    label: "Device type",
    displayAttribute: "model",
    attributes: [
      { name: "model", label: "Model", kind: "Text" },
      { name: "u_height", label: "Height (U)", kind: "Number" },
      { name: "is_full_depth", label: "Full depth", kind: "Boolean" },
      { name: "part_number", label: "Part number", kind: "Text" },
    ],
    relationships: [
      {
        name: "manufacturer",
        label: "Manufacturer",
        peer: "OrganizationManufacturer",
        cardinality: "one",
      },
      { name: "devices", label: "Devices", peer: "DcimDevice", cardinality: "many" },
    ],
  },
  {
    kind: "DcimDeviceRole",
    label: "Device role",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "color", label: "Color", kind: "Text" },
    ],
    relationships: [{ name: "devices", label: "Devices", peer: "DcimDevice", cardinality: "many" }],
  },
  {
    kind: "OrganizationManufacturer",
    label: "Manufacturer",
    displayAttribute: "name",
    attributes: [{ name: "name", label: "Name", kind: "Text" }],
    relationships: [
      { name: "device_types", label: "Device types", peer: "DcimDeviceType", cardinality: "many" },
    ],
  },
  {
    kind: "DcimPatchPanel",
    label: "Patch panel",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "rack_unit", label: "Rack unit", kind: "Number" },
      { name: "size_u", label: "Size (U)", kind: "Number" },
      { name: "mounted_side", label: "Mounted side", kind: "Text" },
      { name: "port_count", label: "Port count", kind: "Number" },
    ],
    relationships: [{ name: "rack", label: "Rack", peer: "DcimRack", cardinality: "one" }],
  },
  {
    kind: "DcimPdu",
    label: "Power distribution unit",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "position", label: "Position", kind: "Number" },
      { name: "height", label: "Height", kind: "Number" },
      { name: "face", label: "Face", kind: "Dropdown", choices: ["front", "rear"] },
      { name: "phase", label: "Phase", kind: "Text" },
    ],
    relationships: [{ name: "rack", label: "Rack", peer: "DcimRack", cardinality: "one" }],
  },
  {
    kind: "LocationRack",
    label: "Location rack",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "height", label: "Height", kind: "Text" },
      { name: "facility_id", label: "Facility ID", kind: "Text" },
      { name: "status", label: "Status", kind: "Dropdown", choices: STATUS },
    ],
    relationships: [
      { name: "site", label: "Site", peer: "LocationSite", cardinality: "one" },
      { name: "servers", label: "Servers", peer: "ComputeServer", cardinality: "many" },
    ],
  },
  {
    kind: "ComputeServer",
    label: "Server",
    displayAttribute: "hostname",
    attributes: [
      { name: "hostname", label: "Hostname", kind: "Text" },
      { name: "rack_slot", label: "Rack slot", kind: "Text" },
      { name: "mount_side", label: "Mount side", kind: "Dropdown", choices: ["FRONT", "REAR"] },
      { name: "status", label: "Status", kind: "Dropdown", choices: STATUS },
      { name: "asset_tag", label: "Asset tag", kind: "Text" },
    ],
    relationships: [
      { name: "rack", label: "Rack", peer: "LocationRack", cardinality: "one" },
      { name: "model", label: "Model", peer: "ComputeServerModel", cardinality: "one" },
      { name: "tenant", label: "Tenant", peer: "OrganizationTenant", cardinality: "one" },
    ],
  },
  {
    kind: "ComputeServerModel",
    label: "Server model",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "vendor", label: "Vendor", kind: "Text" },
      { name: "units", label: "Units", kind: "Number" },
      { name: "full_depth", label: "Full depth", kind: "Boolean" },
    ],
    relationships: [
      { name: "servers", label: "Servers", peer: "ComputeServer", cardinality: "many" },
    ],
  },
  {
    kind: "OrganizationTenant",
    label: "Tenant",
    displayAttribute: "name",
    attributes: [
      { name: "name", label: "Name", kind: "Text" },
      { name: "color", label: "Color", kind: "Text" },
    ],
    relationships: [
      { name: "servers", label: "Servers", peer: "ComputeServer", cardinality: "many" },
    ],
  },
];

export const FAKE_SCHEMA: Record<string, SchemaKind> = Object.fromEntries(
  KINDS.map((schemaKind) => [schemaKind.kind, schemaKind])
);
