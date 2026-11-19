import type {
  AttributeValue,
  GraphNode,
  NodeStore,
} from "@/entities/rack-elevation/domain/model/schema";

const nodes: NodeStore = {};

function add(
  id: string,
  kind: string,
  attributes: Record<string, AttributeValue>,
  relationships: Record<string, string | null> = {}
): GraphNode {
  const node: GraphNode = { id, kind, attributes, relationships: { ...relationships } };
  nodes[id] = node;
  return node;
}

function link(fromId: string, relationship: string, toId: string) {
  const from = nodes[fromId];
  if (!from) return;
  const current = from.relationships[relationship];
  from.relationships[relationship] = [...(Array.isArray(current) ? current : []), toId];
}

// Sites, manufacturers, roles, tenants
add("site-ams1", "LocationSite", { name: "AMS1", city: "Amsterdam" });
add("site-fra2", "LocationSite", { name: "FRA2", city: "Frankfurt" });

const MANUFACTURERS: [string, string][] = [
  ["mfr-arista", "Arista"],
  ["mfr-juniper", "Juniper"],
  ["mfr-dell", "Dell"],
  ["mfr-paloalto", "Palo Alto Networks"],
  ["mfr-netapp", "NetApp"],
  ["mfr-opengear", "Opengear"],
];
for (const [id, name] of MANUFACTURERS) {
  add(id, "OrganizationManufacturer", { name });
}

const ROLES: [string, string, string][] = [
  ["role-spine", "spine", "#6366f1"],
  ["role-leaf", "leaf", "#0ea5e9"],
  ["role-firewall", "firewall", "#ef4444"],
  ["role-compute", "compute", "#10b981"],
  ["role-storage", "storage", "#f59e0b"],
  ["role-management", "management", "#64748b"],
];
for (const [id, name, color] of ROLES) {
  add(id, "DcimDeviceRole", { name, color });
}

const DEVICE_TYPES: [string, string, number, boolean, string, string][] = [
  ["dt-7050", "DCS-7050CX3-32S", 1, false, "mfr-arista", "DCS-7050CX3-32S-R"],
  ["dt-qfx5120", "QFX5120-48Y", 1, false, "mfr-juniper", "QFX5120-48Y-AFI"],
  ["dt-pa3220", "PA-3220", 2, true, "mfr-paloalto", "PAN-PA-3220"],
  ["dt-r750", "PowerEdge R750", 2, true, "mfr-dell", "R750-XS"],
  ["dt-r650", "PowerEdge R650", 1, true, "mfr-dell", "R650-XS"],
  ["dt-a400", "AFF A400", 4, true, "mfr-netapp", "AFF-A400"],
  ["dt-cm8100", "CM8100", 1, false, "mfr-opengear", "CM8100-10G"],
];
for (const [id, model, uHeight, isFullDepth, manufacturer, partNumber] of DEVICE_TYPES) {
  add(
    id,
    "DcimDeviceType",
    { model, u_height: uHeight, is_full_depth: isFullDepth, part_number: partNumber },
    { manufacturer }
  );
  link(manufacturer, "device_types", id);
}

// DcimRack: height comes from the rack type, objects come from three relationships
add("rt-42", "DcimRackType", { model: "APC NetShelter SX 42U", u_count: 42, width: "19in" });
add("rt-48", "DcimRackType", { model: "APC NetShelter SX 48U", u_count: 48, width: "19in" });

const DCIM_RACKS: [string, string, string, string, string][] = [
  ["rack-r101", "AMS1-R101", "rt-42", "site-ams1", "SN-R101-7731"],
  ["rack-r102", "AMS1-R102", "rt-48", "site-ams1", "SN-R102-7732"],
];
for (const [id, name, rackType, site, serialNumber] of DCIM_RACKS) {
  add(
    id,
    "DcimRack",
    { name, serial_number: serialNumber, status: "active" },
    { rack_type: rackType, site }
  );
  link(rackType, "racks", id);
  link(site, "racks", id);
}

const DEVICES: [string, string, string, string, number | null, "front" | "rear", string][] = [
  ["rack-r101", "ams1-spine-01", "dt-7050", "role-spine", 40, "front", "active"],
  ["rack-r101", "ams1-spine-02", "dt-7050", "role-spine", 39, "front", "active"],
  ["rack-r101", "ams1-leaf-01", "dt-qfx5120", "role-leaf", 36, "front", "active"],
  ["rack-r101", "ams1-leaf-02", "dt-qfx5120", "role-leaf", 35, "front", "active"],
  ["rack-r101", "ams1-fw-01", "dt-pa3220", "role-firewall", 30, "front", "active"],
  ["rack-r101", "ams1-esx-01", "dt-r750", "role-compute", 20, "front", "active"],
  ["rack-r101", "ams1-esx-02", "dt-r750", "role-compute", 18, "front", "active"],
  ["rack-r101", "ams1-esx-03", "dt-r750", "role-compute", 16, "front", "maintenance"],
  ["rack-r101", "ams1-esx-04", "dt-r750", "role-compute", 14, "front", "planned"],
  ["rack-r101", "ams1-esx-05", "dt-r650", "role-compute", 15, "rear", "planned"],
  ["rack-r101", "ams1-nas-01", "dt-a400", "role-storage", 6, "front", "active"],
  ["rack-r101", "ams1-oob-01", "dt-cm8100", "role-management", 42, "rear", "active"],
  ["rack-r101", "ams1-leaf-03", "dt-qfx5120", "role-leaf", null, "front", "planned"],
  ["rack-r102", "ams1-spine-03", "dt-7050", "role-spine", 46, "front", "planned"],
  ["rack-r102", "ams1-esx-11", "dt-r650", "role-compute", 30, "front", "active"],
  ["rack-r102", "ams1-esx-12", "dt-r650", "role-compute", 29, "front", "active"],
  ["rack-r102", "ams1-esx-13", "dt-r750", "role-compute", 26, "front", "active"],
  ["rack-r102", "ams1-oob-02", "dt-cm8100", "role-management", 48, "rear", "active"],
];
for (const [index, [rack, name, deviceType, role, position, face, status]] of DEVICES.entries()) {
  const id = `dev-${name}`;
  add(
    id,
    "DcimDevice",
    { name, position, face, status, serial_number: `JPE${String(41_020 + index * 37)}` },
    { rack, device_type: deviceType, role }
  );
  link(rack, "devices", id);
  link(deviceType, "devices", id);
  link(role, "devices", id);
}

const PATCH_PANELS: [string, string, number, number, string, number][] = [
  ["rack-r101", "PP-R101-A", 38, 1, "FRONT", 24],
  ["rack-r101", "PP-R101-B", 37, 1, "BACK", 24],
  ["rack-r101", "PP-R101-C", 1, 2, "FRONT", 48],
  ["rack-r102", "PP-R102-A", 44, 1, "FRONT", 24],
];

for (const [rack, name, rackUnit, sizeU, side, portCount] of PATCH_PANELS) {
  const id = `pp-${name}`;
  add(
    id,
    "DcimPatchPanel",
    { name, rack_unit: rackUnit, size_u: sizeU, mounted_side: side, port_count: portCount },
    { rack }
  );
  link(rack, "patch_panels", id);
}

const PDUS: [string, string, number, string][] = [
  ["rack-r101", "PDU-R101-A", 24, "A"],
  ["rack-r101", "PDU-R101-B", 23, "B"],
  ["rack-r102", "PDU-R102-A", 20, "A"],
];
for (const [rack, name, position, phase] of PDUS) {
  const id = `pdu-${name}`;
  add(id, "DcimPdu", { name, position, height: 1, face: "rear", phase }, { rack });
  link(rack, "pdus", id);
}

// LocationRack: a different schema with text heights ("42"), text slots ("U12") and uppercase sides
add(
  "lr-fra2-07",
  "LocationRack",
  { name: "FRA2-07", height: "42", facility_id: "FRA2-HALL3-07", status: "active" },
  { site: "site-fra2" }
);
link("site-fra2", "location_racks", "lr-fra2-07");

const TENANTS: [string, string, string][] = [
  ["tenant-acme", "Acme Corp", "#8b5cf6"],
  ["tenant-globex", "Globex", "#f97316"],
  ["tenant-internal", "Internal IT", "#14b8a6"],
];
for (const [id, name, color] of TENANTS) {
  add(id, "OrganizationTenant", { name, color });
}

for (const [id, name, vendor, units, fullDepth] of [
  ["sm-sys-1029", "SYS-1029U", "Supermicro", 1, true],
  ["sm-sys-2049", "SYS-2049U", "Supermicro", 2, true],
  ["sm-dl380", "ProLiant DL380 Gen11", "HPE", 2, true],
  ["sm-cable-mgmt", "1U cable manager", "Generic", 1, false],
] as const) {
  add(id, "ComputeServerModel", { name, vendor, units, full_depth: fullDepth });
}

const SERVERS: [string, string | null, "FRONT" | "REAR", string, string][] = [
  ["fra2-web-01", "U40", "FRONT", "sm-sys-1029", "tenant-acme"],
  ["fra2-web-02", "U39", "FRONT", "sm-sys-1029", "tenant-acme"],
  ["fra2-db-01", "U34", "FRONT", "sm-dl380", "tenant-globex"],
  ["fra2-db-02", "U32", "FRONT", "sm-dl380", "tenant-globex"],
  ["fra2-hv-01", "U24", "FRONT", "sm-sys-2049", "tenant-internal"],
  ["fra2-hv-02", "U22", "FRONT", "sm-sys-2049", "tenant-internal"],
  ["fra2-cbl-01", "U38", "REAR", "sm-cable-mgmt", "tenant-internal"],
  ["fra2-hv-03", null, "FRONT", "sm-sys-2049", "tenant-internal"],
];
for (const [index, [hostname, slot, side, model, tenant]] of SERVERS.entries()) {
  const id = `srv-${hostname}`;
  add(
    id,
    "ComputeServer",
    {
      hostname,
      rack_slot: slot,
      mount_side: side,
      status: "active",
      asset_tag: `FRA-${String(9100 + index)}`,
    },
    { rack: "lr-fra2-07", model, tenant }
  );
  link("lr-fra2-07", "servers", id);
  link(model, "servers", id);
  link(tenant, "servers", id);
}

export const FAKE_NODES: NodeStore = nodes;
