// @ts-nocheck
// Throwaway prototype data + fake search engines. Deleted after the decision.

export type FieldKind = "text" | "textarea" | "number" | "dropdown" | "password";

export type Field = { name: string; label: string; value: string; kind: FieldKind };
export type Peer = { name: string; label: string; value: string; kind: string };

export type ProtoNode = {
  id: string;
  kind: string;
  label: string;
  context?: string;
  fields: Field[];
  peers: Peer[];
  ipNamespace?: string;
};

export type KindMeta = {
  label: string;
  plural: string;
  namespace: string;
  icon: string;
  weight: number;
};

export const KINDS: Record<string, KindMeta> = {
  LocationSite: { label: "Site", plural: "Sites", namespace: "Location", icon: "mdi:map-marker-radius-outline", weight: 45 },
  InfraDevice: { label: "Device", plural: "Devices", namespace: "Infra", icon: "mdi:server", weight: 40 },
  OrganizationProvider: { label: "Provider", plural: "Providers", namespace: "Organization", icon: "mdi:domain", weight: 35 },
  InfraCircuit: { label: "Circuit", plural: "Circuits", namespace: "Infra", icon: "mdi:cable-data", weight: 30 },
  IpamIPPrefix: { label: "IP Prefix", plural: "IP Prefixes", namespace: "Ipam", icon: "mdi:ip-network-outline", weight: 30 },
  IpamIPAddress: { label: "IP Address", plural: "IP Addresses", namespace: "Ipam", icon: "mdi:ip-outline", weight: 25 },
  InfraVLAN: { label: "VLAN", plural: "VLANs", namespace: "Infra", icon: "mdi:lan-pending", weight: 20 },
  InfraInterfaceL3: { label: "Interface L3", plural: "Interfaces L3", namespace: "Infra", icon: "mdi:ethernet", weight: 10 },
  CoreAccount: { label: "Account", plural: "Accounts", namespace: "Core", icon: "mdi:account", weight: 0 },
};

export const IP_NAMESPACES = ["default", "customer-acme-europe-production"];

// ---------- deterministic generator ----------

function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(42);
const hex = (n: number) =>
  Array.from({ length: n }, () => Math.floor(rand() * 16).toString(16)).join("");
const uuid = () => `${hex(8)}-${hex(4)}-${hex(4)}-${hex(4)}-${hex(12)}`;
const pick = <T,>(arr: T[]) => arr[Math.floor(rand() * arr.length)];
const serial = (prefix: string) =>
  prefix +
  Array.from({ length: 8 }, () => "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"[Math.floor(rand() * 34)]).join("");

const f = (name: string, label: string, value: string | number, kind: FieldKind = "text"): Field => ({
  name,
  label,
  value: String(value),
  kind,
});

const SITES = [
  { code: "atl1", city: "Atlanta", country: "United States", facility: "Equinix AT1", tz: "America/New_York" },
  { code: "ord1", city: "Chicago", country: "United States", facility: "Equinix CH1", tz: "America/Chicago" },
  { code: "jfk1", city: "New York", country: "United States", facility: "Equinix NY5", tz: "America/New_York" },
  { code: "den1", city: "Denver", country: "United States", facility: "Flexential Denver North", tz: "America/Denver" },
  { code: "dfw1", city: "Dallas", country: "United States", facility: "Equinix DA6", tz: "America/Chicago" },
  {
    code: "fra1-frankfurt-equinix-fr5-cage-12",
    city: "Frankfurt am Main",
    country: "Germany",
    facility: "Equinix FR5, Cage 12, Suite 4 (shared meet-me room with Interxion FRA8)",
    tz: "Europe/Berlin",
  },
];

const PROVIDERS = [
  { name: "Lumen Technologies", asn: 3356, prefix: "DUFF" },
  { name: "Zayo Group", asn: 6461, prefix: "ZYO" },
  { name: "Cogent Communications", asn: 174, prefix: "CGNT" },
  { name: "Arelion (formerly Telia Carrier)", asn: 1299, prefix: "IC" },
];

const ROLES = [
  { suffix: "edge1", role: "edge", platform: "Cisco IOS XR 7.9.2" },
  { suffix: "edge2", role: "edge", platform: "Cisco IOS XR 7.9.2" },
  { suffix: "core1", role: "core", platform: "Juniper Junos 23.2R1" },
  { suffix: "core2", role: "core", platform: "Juniper Junos 23.2R1" },
  { suffix: "leaf01", role: "leaf", platform: "Arista EOS 4.31.2F" },
  { suffix: "leaf02", role: "leaf", platform: "Arista EOS 4.31.2F" },
  { suffix: "leaf03", role: "leaf", platform: "Arista EOS 4.31.2F" },
  { suffix: "leaf04", role: "leaf", platform: "Arista EOS 4.31.2F" },
];

export const NODES: ProtoNode[] = [];

for (const p of PROVIDERS) {
  NODES.push({
    id: uuid(),
    kind: "OrganizationProvider",
    label: p.name,
    fields: [
      f("name", "Name", p.name),
      f("description", "Description", `Transit and wavelength provider, AS${p.asn}`, "textarea"),
      f("asn", "ASN", p.asn, "number"),
    ],
    peers: [],
  });
}

NODES.push({
  id: uuid(),
  kind: "IpamIPPrefix",
  label: "10.0.0.0/8",
  fields: [
    f("prefix", "Prefix", "10.0.0.0/8"),
    f("description", "Description", "Private supernet for all sites", "textarea"),
    f("member_type", "Member type", "prefix", "dropdown"),
  ],
  peers: [{ name: "ip_namespace", label: "IP namespace", value: "default", kind: "IpamNamespace" }],
  ipNamespace: "default",
});

let circuitCounter = 0;

SITES.forEach((site, sIdx) => {
  const s = sIdx + 1;
  NODES.push({
    id: uuid(),
    kind: "LocationSite",
    label: site.code,
    fields: [
      f("name", "Name", site.code),
      f("description", "Description", `${site.city}, ${site.facility}`, "textarea"),
      f("city", "City", site.city),
      f("country", "Country", site.country),
      f("timezone", "Time zone", site.tz),
    ],
    peers: [],
  });

  const ns = "default";
  const prefixes: Array<[string, string, string]> = [
    [`10.${s}.0.0/16`, `${site.city} site container`, "prefix"],
    [`10.${s}.0.0/24`, `${site.code} loopbacks`, "address"],
    [`10.${s}.1.0/24`, `${site.code} out-of-band management`, "address"],
    [`10.${s}.2.0/24`, `${site.code} point-to-point links`, "address"],
  ];
  for (const [prefix, description, member] of prefixes) {
    NODES.push({
      id: uuid(),
      kind: "IpamIPPrefix",
      label: prefix,
      fields: [
        f("prefix", "Prefix", prefix),
        f("description", "Description", description, "textarea"),
        f("member_type", "Member type", member, "dropdown"),
      ],
      peers: [
        { name: "ip_namespace", label: "IP namespace", value: ns, kind: "IpamNamespace" },
        { name: "site", label: "Site", value: site.code, kind: "LocationSite" },
      ],
      ipNamespace: ns,
    });
  }
  if (s === 1) {
    NODES.push({
      id: uuid(),
      kind: "IpamIPPrefix",
      label: "10.1.0.0/24",
      fields: [
        f("prefix", "Prefix", "10.1.0.0/24"),
        f("description", "Description", "ACME Europe production servers (overlaps with atl1 loopbacks)", "textarea"),
        f("member_type", "Member type", "address", "dropdown"),
      ],
      peers: [{ name: "ip_namespace", label: "IP namespace", value: IP_NAMESPACES[1], kind: "IpamNamespace" }],
      ipNamespace: IP_NAMESPACES[1],
    });
  }

  for (const [vid, name, role] of [
    [100, "server", "server"],
    [200, "storage", "storage"],
    [300, "mgmt", "management"],
    [4000, "transit", "transit"],
  ] as const) {
    NODES.push({
      id: uuid(),
      kind: "InfraVLAN",
      label: `${site.code}_${name}`,
      fields: [
        f("name", "Name", `${site.code}_${name}`),
        f("vlan_id", "VLAN ID", vid, "number"),
        f("description", "Description", `${site.city} ${role} VLAN`, "textarea"),
        f("role", "Role", role, "dropdown"),
        f("status", "Status", "active", "dropdown"),
      ],
      peers: [{ name: "site", label: "Site", value: site.code, kind: "LocationSite" }],
    });
  }

  for (let c = 0; c < 2; c++) {
    const provider = PROVIDERS[circuitCounter % PROVIDERS.length];
    circuitCounter++;
    const num = 2245961 + circuitCounter * 7919;
    const circuitId =
      provider.prefix === "ZYO"
        ? `ZYO-OGYX/${num}//ZYO`
        : provider.prefix === "IC"
          ? `IC-${num}-TELIA`
          : `${provider.prefix}-${num}`;
    NODES.push({
      id: uuid(),
      kind: "InfraCircuit",
      label: circuitId,
      fields: [
        f("circuit_id", "Circuit ID", circuitId),
        f("vendor_id", "Vendor ID", serial("VND-")),
        f("description", "Description", `Internet transit 10G, ${site.city}`, "textarea"),
        f("status", "Status", c === 0 ? "active" : "provisioning", "dropdown"),
      ],
      peers: [
        { name: "provider", label: "Provider", value: provider.name, kind: "OrganizationProvider" },
        { name: "site", label: "Site", value: site.code, kind: "LocationSite" },
      ],
    });
  }

  ROLES.forEach((r, dIdx) => {
    const d = dIdx + 1;
    const deviceName = `${site.code}-${r.suffix}`;
    NODES.push({
      id: uuid(),
      kind: "InfraDevice",
      label: deviceName,
      fields: [
        f("name", "Name", deviceName),
        f("description", "Description", `${r.role[0].toUpperCase()}${r.role.slice(1)} router, ${site.facility}`, "textarea"),
        f("serial", "Serial number", serial(r.role === "leaf" ? "JPE" : r.role === "edge" ? "FOC" : "WS")),
        f("role", "Role", r.role, "dropdown"),
        f("status", "Status", pick(["active", "active", "active", "provisioning", "maintenance"]), "dropdown"),
        f("asset_tag", "Asset tag", `AT-${String(s * 100 + d).padStart(5, "0")}`),
      ],
      peers: [
        { name: "site", label: "Site", value: site.code, kind: "LocationSite" },
        { name: "platform", label: "Platform", value: r.platform, kind: "InfraPlatform" },
      ],
    });

    const interfaces = [
      ...Array.from({ length: 8 }, (_, i) => `Ethernet${i + 1}`),
      "Loopback0",
      "Management0",
    ];
    interfaces.forEach((ifName, iIdx) => {
      let description = "";
      if (ifName === "Loopback0") description = "Router ID";
      else if (ifName === "Management0") description = "Out-of-band management";
      else if (r.role !== "leaf" && iIdx < 2) description = `Uplink to ${site.code}-${r.role === "edge" ? "core" : "edge"}${iIdx + 1} Ethernet${d}`;
      else if (r.role === "edge" && iIdx === 2) description = `Internet transit via ${PROVIDERS[(s + d) % PROVIDERS.length].name}`;
      else if (r.role === "leaf" && iIdx < 2) description = `Uplink to ${site.code}-core${iIdx + 1}`;
      else if (rand() > 0.4) description = `Server port, rack ${String.fromCharCode(65 + (iIdx % 4))}${d}`;

      const node: ProtoNode = {
        id: uuid(),
        kind: "InfraInterfaceL3",
        label: ifName,
        context: deviceName,
        fields: [
          f("name", "Name", ifName),
          f("hfid", "Human-friendly ID", `${deviceName} ${ifName}`),
          f("description", "Description", description, "textarea"),
          f("speed", "Speed", ifName.startsWith("Ethernet") ? pick(["100 Gbps", "10 Gbps", "25 Gbps"]) : "1 Gbps"),
          f("mtu", "MTU", ifName === "Management0" ? 1500 : 9214, "number"),
          f("status", "Status", pick(["active", "active", "active", "maintenance", "disabled"]), "dropdown"),
          f("role", "Role", ifName.startsWith("Ethernet") && iIdx < 2 ? "backbone" : ifName === "Loopback0" ? "loopback" : "server", "dropdown"),
        ],
        peers: [{ name: "device", label: "Device", value: deviceName, kind: "InfraDevice" }],
      };
      NODES.push(node);

      let address: string | null = null;
      if (ifName === "Loopback0") address = `10.${s}.0.${d}/32`;
      if (ifName === "Management0") address = `10.${s}.1.${10 + d}/24`;
      if (ifName === "Ethernet1" && r.role !== "leaf") address = `10.${s}.2.${d * 2}/31`;
      if (address) {
        NODES.push({
          id: uuid(),
          kind: "IpamIPAddress",
          label: address,
          context: `${deviceName} ${ifName}`,
          fields: [
            f("address", "Address", address),
            f("description", "Description", `${deviceName} ${ifName}`, "textarea"),
          ],
          peers: [
            { name: "interface", label: "Interface", value: `${deviceName} ${ifName}`, kind: "InfraInterfaceL3" },
            { name: "ip_namespace", label: "IP namespace", value: "default", kind: "IpamNamespace" },
          ],
          ipNamespace: "default",
        });
      }
    });
  });
});

for (const [name, label, type, password] of [
  ["admin", "Administrator", "User", "infrahub-admin-2024"],
  ["automation-bot", "Automation bot", "Script", "atl1-ord1-sync-token"],
  ["netops-atl1-readonly", "NetOps Atlanta (read only)", "User", "Edge1!Atl1"],
]) {
  NODES.push({
    id: uuid(),
    kind: "CoreAccount",
    label: name,
    fields: [
      f("name", "Name", name),
      f("label", "Label", label),
      f("account_type", "Type", type, "dropdown"),
      f("password", "Password", password, "password"),
    ],
    peers: [],
  });
}

export const nodeById = new Map(NODES.map((n) => [n.id, n]));

// ---------- IP helpers ----------

const ipToInt = (ip: string) =>
  ip.split(".").reduce((acc, octet) => (acc << 8) + Number(octet), 0) >>> 0;
const IPV4 = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;

export function parentPrefixesOf(q: string): ProtoNode[] {
  const ip = q.trim().split("/")[0];
  if (!IPV4.test(ip)) return [];
  const target = ipToInt(ip);
  return NODES.filter((n) => n.kind === "IpamIPPrefix")
    .filter((n) => {
      const [net, len] = n.label.split("/");
      const mask = Number(len) === 0 ? 0 : (~0 << (32 - Number(len))) >>> 0;
      return (target & mask) === (ipToInt(net) & mask);
    })
    .sort((a, b) => Number(b.label.split("/")[1]) - Number(a.label.split("/")[1]));
}

// ---------- engines ----------

function valueMatches(value: string, needle: string, caseSensitive: boolean) {
  return caseSensitive ? value.includes(needle) : value.toLowerCase().includes(needle.toLowerCase());
}

function valueEquals(value: string, needle: string, caseSensitive: boolean) {
  return caseSensitive ? value === needle : value.toLowerCase() === needle.toLowerCase();
}

export function isExact(node: ProtoNode, q: string, caseSensitive = false) {
  const needle = q.trim();
  return node.fields.some((fl) => fl.value && valueEquals(fl.value, needle, caseSensitive));
}

const byId = (a: ProtoNode, b: ProtoNode) => a.id.localeCompare(b.id);

function partialMatches(q: string, caseSensitive: boolean) {
  const needle = q.trim();
  return NODES.filter((n) => n.fields.some((fl) => fl.value && valueMatches(fl.value, needle, caseSensitive))).sort(byId);
}

export type SpikeResult = {
  nodes: ProtoNode[];
  /** True when the query returned limit + 1 rows, so more exist than shown. */
  hasMore: boolean;
  /** Real total, only available with the count change from PR #8448. */
  total: number;
  parentPrefixes: ProtoNode[];
};

function page(list: ProtoNode[], limit: number, q: string): SpikeResult {
  const nodes = limit === 0 ? list : list.slice(0, limit);
  return {
    nodes,
    hasMore: limit !== 0 && list.length > limit,
    total: list.length,
    parentPrefixes: parentPrefixesOf(q.trim()).slice(0, 4),
  };
}

/** Today: partial match, ordered by id, first 4. */
export function searchToday(q: string, caseSensitive: boolean) {
  return page(partialMatches(q, caseSensitive), 4, q);
}

/** Partial match query changed to return exact matches first. `limit: 0` returns every match. */
export function searchExactFirst(q: string, caseSensitive: boolean, limit: number) {
  const all = partialMatches(q, caseSensitive);
  const exact = all.filter((n) => isExact(n, q, caseSensitive));
  const rest = all.filter((n) => !isExact(n, q, caseSensitive));
  return page([...exact, ...rest], limit, q);
}

/** The existing exact match query (partial_match: false). */
export function searchExactOnly(q: string, caseSensitive: boolean, limit: number) {
  return page(partialMatches(q, caseSensitive).filter((n) => isExact(n, q, caseSensitive)), limit, q);
}

/** The partial match query, without the nodes the exact query already returned. */
export function searchPartialOnly(q: string, caseSensitive: boolean, limit: number) {
  return page(partialMatches(q, caseSensitive).filter((n) => !isExact(n, q, caseSensitive)), limit, q);
}

// ---------- secondary sources ----------

export const GO_TO = [
  { label: "Devices", path: "/objects/InfraDevice", section: "Menu" },
  { label: "Interfaces", path: "/objects/InfraInterface", section: "Menu" },
  { label: "IP Prefixes", path: "/ipam/prefixes", section: "Menu" },
  { label: "IP Addresses", path: "/ipam/addresses", section: "Menu" },
  { label: "Sites", path: "/objects/LocationSite", section: "Menu" },
  { label: "Circuits", path: "/objects/InfraCircuit", section: "Menu" },
  { label: "VLANs", path: "/objects/InfraVLAN", section: "Menu" },
  { label: "Providers", path: "/objects/OrganizationProvider", section: "Menu" },
  { label: "Proposed changes", path: "/proposed-changes", section: "Menu" },
  { label: "Branches", path: "/branches", section: "Menu" },
  { label: "Tasks", path: "/tasks", section: "Menu" },
];

export const DOCS = [
  { title: "Search for objects in the web interface", breadcrumb: ["Guides", "Web interface"] },
  { title: "Create and manage IP prefixes", breadcrumb: ["Guides", "IPAM"] },
  { title: "IP namespaces", breadcrumb: ["Topics", "IPAM"] },
  { title: "Device lifecycle and status", breadcrumb: ["Topics", "Schema"] },
  { title: "Interfaces and human-friendly IDs", breadcrumb: ["Topics", "Schema"] },
  { title: "Branches and proposed changes", breadcrumb: ["Topics", "Version control"] },
  { title: "Object permissions", breadcrumb: ["Topics", "Permissions"] },
  { title: "Circuits and providers", breadcrumb: ["Reference", "Schema library"] },
];

export function searchGoTo(q: string) {
  const needle = q.trim().toLowerCase();
  if (!needle) return [];
  return GO_TO.filter((g) => g.label.toLowerCase().includes(needle)).slice(0, 3);
}

export function searchDocs(q: string) {
  const tokens = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!tokens.length) return [];
  return DOCS.filter((d) => tokens.some((t) => d.title.toLowerCase().includes(t))).slice(0, 3);
}
