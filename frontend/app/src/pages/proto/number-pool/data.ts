// PROTO number-pool — throwaway fake data for /proto/number-pool. Delete with the prototype.

// a range with no weight counts as 0; equal weights use the lowest start first
export type Range = { id: string; weight: number | null; start: number; end: number };

export type Usage = { defaultUsed: number; branchUsed: number; total: number };

// a scope entry is a required cardinality-one relationship or a required scalar attribute
export type ScopeRelation = { name: string; label: string };

type ScopePeer = { relation: string; label: string; kind: string; id: string };

export type Scope = {
  id: string;
  peers: ScopePeer[];
  rangeUsage: Usage[];
  usage: Usage;
};

export type Allocation = {
  number: number;
  objectLabel: string;
  objectId: string;
  kind: string;
  branch: string;
  rangeId: string;
  source: "Allocated" | "Provided";
};

export type Pool = {
  id: string;
  name: string;
  description: string;
  targetKind: string;
  targetAttribute: string;
  schemaDefined: boolean;
  scopedBy: ScopeRelation[];
  attributeLimits: { min: number; max: number };
};

export type Dataset = {
  key: string;
  label: string;
  pool: Pool;
  ranges: Range[];
  kinds: string[];
  objectLabel: (n: number, rng: () => number) => string;
  scopes: Scope[] | null;
  // unscoped pools are a single implicit scope
  implicitScope: Scope | null;
};

const BRANCHES = ["main", "feature/fabric-pod-3-rollout", "fix-ams2-vrf", "add-customer-acme"];

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d_2b_79_f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4_294_967_296;
  };
}

function hash(s: string) {
  let h = 2_166_136_261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16_777_619);
  }
  return h >>> 0;
}

export function sortRanges(ranges: Range[]) {
  return [...ranges].sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0) || a.start - b.start);
}

export const weightLabel = (r: Range) => (r.weight === null ? "No weight" : `Weight ${r.weight}`);

const rangeSize = (r: Range) => r.end - r.start + 1;

const sum = (usages: Usage[]): Usage =>
  usages.reduce(
    (acc, u) => ({
      defaultUsed: acc.defaultUsed + u.defaultUsed,
      branchUsed: acc.branchUsed + u.branchUsed,
      total: acc.total + u.total,
    }),
    { defaultUsed: 0, branchUsed: 0, total: 0 }
  );

// Fill ranges in weight order, the way the backend would.
function fillUsage(ranges: Range[], used: number, branchShare: number): Usage[] {
  let remaining = used;
  return sortRanges(ranges).map((r) => {
    const size = rangeSize(r);
    const take = Math.min(size, remaining);
    remaining -= take;
    const branchUsed = Math.round(take * branchShare);
    return { defaultUsed: take - branchUsed, branchUsed, total: size };
  });
}

function makeScope(
  ranges: Range[],
  id: string,
  peers: ScopePeer[],
  used: number,
  branchShare: number
): Scope {
  const rangeUsage = fillUsage(ranges, used, branchShare);
  return { id, peers, rangeUsage, usage: sum(rangeUsage) };
}

const SITES = ["par1", "ams2", "fra1", "lon3", "nyc1", "sjc2", "sin1", "syd1", "dub1", "mad2"];
const ROLES = ["leaf", "spine", "border-leaf", "edge-router", "core-spine-interconnect"];
const VRFS = [
  "blue",
  "red",
  "mgmt",
  "internet",
  "customer-acme-internet-transit",
  "customer-globex-l3vpn",
  "storage-replication",
];

function buildDeviceVrfScopes(ranges: Range[]): Scope[] {
  const rng = mulberry32(7);
  const scopes: Scope[] = [];
  const capacity = ranges.reduce((acc, r) => acc + rangeSize(r), 0);
  let d = 0;
  while (scopes.length < 1240) {
    const site = SITES[d % SITES.length]!;
    const role = ROLES[Math.floor(rng() * ROLES.length)]!;
    const device = `${site}-${role}-${String(Math.floor(d / SITES.length) + 1).padStart(3, "0")}`;
    const vrfCount = 1 + Math.floor(rng() * 4);
    const vrfs = [...VRFS].sort(() => rng() - 0.5).slice(0, vrfCount);
    for (const vrf of vrfs) {
      const r = rng();
      const ratio = r > 0.985 ? 0.9 + rng() * 0.1 : r > 0.9 ? 0.4 + rng() * 0.4 : rng() * 0.25;
      scopes.push(
        makeScope(
          ranges,
          `s${scopes.length}`,
          [
            { relation: "device", label: device, kind: "InfraDevice", id: `dev-${d}` },
            { relation: "vrf", label: vrf, kind: "IpamVRF", id: `vrf-${vrf}` },
          ],
          Math.round(capacity * ratio),
          rng() * 0.12
        )
      );
    }
    d++;
  }
  return scopes;
}

function buildSiteScopes(ranges: Range[]): Scope[] {
  const rng = mulberry32(11);
  const cities = [
    "Paris Equinix PA3",
    "Amsterdam Digital Realty AMS17 (cage 4, row B)",
    "Frankfurt Interxion FRA6",
    "London Telehouse North",
    "New York 60 Hudson",
    "San Jose Equinix SV5",
    "Singapore Global Switch",
    "Sydney NextDC S1",
  ];
  const capacity = ranges.reduce((acc, r) => acc + rangeSize(r), 0);
  return Array.from({ length: 86 }, (_, i) => {
    const label = `${cities[i % cities.length]}${i >= cities.length ? ` #${Math.floor(i / cities.length) + 1}` : ""}`;
    return makeScope(
      ranges,
      `s${i}`,
      [{ relation: "site", label, kind: "LocationSite", id: `site-${i}` }],
      Math.round(capacity * rng() ** 2 * 0.6),
      rng() * 0.08
    );
  });
}

const VLAN_ROLES = ["server", "management", "storage", "transit"];

function buildSiteRoleScopes(ranges: Range[]): Scope[] {
  const rng = mulberry32(23);
  const sites = [
    "par1",
    "ams2",
    "fra1",
    "lon3",
    "nyc1",
    "sjc2",
    "sin1",
    "syd1",
    "dub1",
    "mad2",
    "zrh1",
    "waw1",
  ];
  const capacity = ranges.reduce((acc, r) => acc + rangeSize(r), 0);
  const scopes: Scope[] = [];
  sites.forEach((site, i) => {
    for (const role of VLAN_ROLES.filter(() => rng() > 0.25)) {
      scopes.push(
        makeScope(
          ranges,
          `s${scopes.length}`,
          [
            {
              relation: "site",
              label: `${site.toUpperCase()} data center`,
              kind: "LocationSite",
              id: `site-${i}`,
            },
            { relation: "role", label: role, kind: "Dropdown", id: `role-${role}` },
          ],
          Math.round(capacity * rng() * 0.5),
          rng() * 0.1
        )
      );
    }
  });
  // VLANs created before the role was required have an empty role value
  scopes.push(
    makeScope(
      ranges,
      `s${scopes.length}`,
      [
        { relation: "site", label: "PAR1 data center", kind: "LocationSite", id: "site-0" },
        { relation: "role", label: "", kind: "Dropdown", id: "role-empty" },
      ],
      37,
      0
    )
  );
  return scopes;
}

function buildWideScopes(ranges: Range[]): Scope[] {
  const rng = mulberry32(31);
  const capacity = ranges.reduce((acc, r) => acc + rangeSize(r), 0);
  const sites = ["PAR1", "AMS2", "FRA1", "LON3", "NYC1"];
  const tenants = ["acme-corp", "globex-international-holdings", "initech", "umbrella"];
  const vrfs = ["blue", "red", "customer-acme-internet-transit", "mgmt"];
  const roles = ["server", "storage", "management"];
  const scopes: Scope[] = [];
  for (const site of sites) {
    for (let pod = 1; pod <= 3; pod++) {
      for (const tenant of tenants) {
        if (rng() < 0.35) continue;
        const vrf = vrfs[Math.floor(rng() * vrfs.length)]!;
        for (const role of roles.filter(() => rng() > 0.4)) {
          scopes.push(
            makeScope(
              ranges,
              `s${scopes.length}`,
              [
                {
                  relation: "site",
                  label: `${site} data center`,
                  kind: "LocationSite",
                  id: `site-${site}`,
                },
                {
                  relation: "pod",
                  label: `pod-${pod}`,
                  kind: "InfraPod",
                  id: `pod-${site}-${pod}`,
                },
                {
                  relation: "tenant",
                  label: tenant,
                  kind: "OrganizationTenant",
                  id: `tenant-${tenant}`,
                },
                { relation: "vrf", label: vrf, kind: "IpamVRF", id: `vrf-${vrf}` },
                { relation: "role", label: role, kind: "Dropdown", id: `role-${role}` },
              ],
              Math.round(capacity * rng() ** 1.5 * 0.9),
              rng() * 0.1
            )
          );
        }
      }
    }
  }
  return scopes;
}

const wideRanges: Range[] = [{ id: "r1", weight: 100, start: 100, end: 1999 }];

const siteRoleRanges: Range[] = [
  { id: "r1", weight: 200, start: 100, end: 499 },
  { id: "r2", weight: null, start: 1000, end: 1999 },
];

const deviceVrfRanges: Range[] = [
  { id: "r1", weight: 300, start: 100, end: 999 },
  { id: "r2", weight: 200, start: 2000, end: 2999 },
  { id: "r3", weight: 100, start: 3500, end: 3999 },
];

const siteRanges: Range[] = [{ id: "r1", weight: 100, start: 1, end: 9999 }];

const asnRanges: Range[] = [
  { id: "r2", weight: 100, start: 4_200_000_000, end: 4_294_967_294 },
  { id: "r1", weight: 200, start: 64_512, end: 65_534 },
];

const loopbackRanges: Range[] = [
  { id: "r1", weight: 100, start: 0, end: 255 },
  { id: "r2", weight: 100, start: 1000, end: 1255 },
];

export const DATASETS: Dataset[] = [
  {
    key: "device-vrf",
    label: "Device + VRF",
    pool: {
      id: "18a7f2c4-0b3e-4f6a-9c11-7d2e5a8b9f01",
      name: "Subinterface unit IDs per device and VRF",
      description:
        "Unit numbers for L2 and L3 subinterfaces. Every device and VRF pair gets its own sequence, so the same unit can be reused on another device.",
      targetKind: "InfraSubinterface",
      targetAttribute: "unit_id",
      schemaDefined: false,
      scopedBy: [
        { name: "device", label: "Device" },
        { name: "vrf", label: "VRF" },
      ],
      attributeLimits: { min: 0, max: 16_383 },
    },
    ranges: deviceVrfRanges,
    kinds: ["InfraSubinterfaceL3", "InfraSubinterfaceL2"],
    objectLabel: (n, rng) => `${rng() > 0.5 ? "xe" : "ge"}-0/0/${Math.floor(rng() * 48)}.${n}`,
    scopes: buildDeviceVrfScopes(deviceVrfRanges),
    implicitScope: null,
  },
  {
    key: "site",
    label: "Site",
    pool: {
      id: "2b9e6d10-55a4-4c0e-8f3b-1a7c9e2d4b60",
      name: "Circuit numbers per site",
      description: "Provider circuit references, numbered per site.",
      targetKind: "InfraCircuit",
      targetAttribute: "circuit_number",
      schemaDefined: false,
      scopedBy: [{ name: "site", label: "Site" }],
      attributeLimits: { min: 1, max: 99_999 },
    },
    ranges: siteRanges,
    kinds: ["InfraCircuit"],
    objectLabel: (n) => `CIR-${String(n).padStart(5, "0")}`,
    scopes: buildSiteScopes(siteRanges),
    implicitScope: null,
  },
  {
    key: "asn",
    label: "Schema pool",
    pool: {
      id: "18a7f2c4-9d1e-4b6a-a0c3-5e2f7b9d4c11",
      name: "InfraAutonomousSystem.asn [18a7f2c4-9d1e-4b6a-a0c3-5e2f7b9d4c11]",
      description: "",
      targetKind: "InfraAutonomousSystem",
      targetAttribute: "asn",
      schemaDefined: true,
      scopedBy: [],
      attributeLimits: { min: 1, max: 4_294_967_294 },
    },
    ranges: asnRanges,
    kinds: ["InfraAutonomousSystem"],
    objectLabel: (n) => `AS${n}`,
    scopes: null,
    implicitScope: makeScope(asnRanges, "implicit", [], 1020 + 23_333, 0.04),
  },
  {
    key: "empty",
    label: "Empty",
    pool: {
      id: "7c0d3e88-1f2a-4b5c-9d6e-0a1b2c3d4e5f",
      name: "Loopback IDs",
      description: "Loopback interface numbers for every device.",
      targetKind: "InfraDevice",
      targetAttribute: "loopback_id",
      schemaDefined: false,
      scopedBy: [],
      attributeLimits: { min: 0, max: 4095 },
    },
    ranges: loopbackRanges,
    kinds: ["InfraDevice"],
    objectLabel: (n) => `loopback${n}`,
    scopes: null,
    implicitScope: makeScope(loopbackRanges, "implicit", [], 0, 0),
  },
  {
    key: "site-role",
    label: "Site + role",
    pool: {
      id: "5d1f0a7e-3c2b-4e9d-8a61-2f4b7c9e0d13",
      name: "Server VLANs per site and role",
      description:
        "VLAN IDs for top-of-rack networks. Each site and VLAN role has its own sequence.",
      targetKind: "InfraVLAN",
      targetAttribute: "vlan_id",
      schemaDefined: false,
      scopedBy: [
        { name: "site", label: "Site" },
        { name: "role", label: "Role" },
      ],
      attributeLimits: { min: 1, max: 4094 },
    },
    ranges: siteRoleRanges,
    kinds: ["InfraVLAN"],
    objectLabel: (n) => `vlan${n}`,
    scopes: buildSiteRoleScopes(siteRoleRanges),
    implicitScope: null,
  },
  {
    key: "five-fields",
    label: "5 scope fields",
    pool: {
      id: "c3a9e1f2-6d4b-4a7c-9e08-2b5f1d7c3e94",
      name: "Tenant VLANs per site, pod, tenant, VRF and role",
      description:
        "VLAN IDs for tenant networks. Every combination of site, pod, tenant, VRF and role has its own sequence.",
      targetKind: "InfraVLAN",
      targetAttribute: "vlan_id",
      schemaDefined: false,
      scopedBy: [
        { name: "site", label: "Site" },
        { name: "pod", label: "Pod" },
        { name: "tenant", label: "Tenant" },
        { name: "vrf", label: "VRF" },
        { name: "role", label: "Role" },
      ],
      attributeLimits: { min: 1, max: 4094 },
    },
    ranges: wideRanges,
    kinds: ["InfraVLAN"],
    objectLabel: (n) => `vlan${n}`,
    scopes: buildWideScopes(wideRanges),
    implicitScope: null,
  },
  {
    key: "one-scope",
    label: "One scope",
    pool: {
      id: "4f1b8c2d-9a3e-4d7f-b6c0-8e2a5d1f9c37",
      name: "Circuit numbers per site (pilot)",
      description: "Pilot pool: only one site has circuits so far.",
      targetKind: "InfraCircuit",
      targetAttribute: "circuit_number",
      schemaDefined: false,
      scopedBy: [{ name: "site", label: "Site" }],
      attributeLimits: { min: 1, max: 99_999 },
    },
    ranges: siteRanges,
    kinds: ["InfraCircuit"],
    objectLabel: (n) => `CIR-${String(n).padStart(5, "0")}`,
    scopes: buildSiteScopes(siteRanges).slice(0, 1),
    implicitScope: null,
  },
  {
    key: "no-ranges",
    label: "No ranges",
    pool: {
      id: "9e4c2a61-7b0d-4f3e-a5c8-1d6b9f2e7a40",
      name: "Legacy circuit IDs",
      description:
        "Kept for circuits created before the provider pools. Its last range was removed.",
      targetKind: "InfraCircuit",
      targetAttribute: "legacy_id",
      schemaDefined: false,
      scopedBy: [],
      attributeLimits: { min: 1, max: 99_999 },
    },
    ranges: [],
    kinds: ["InfraCircuit"],
    objectLabel: (n) => `LEG-${n}`,
    scopes: null,
    implicitScope: makeScope([], "implicit", [], 0, 0),
  },
];

const allocationCache = new Map<string, Allocation[]>();

export function getAllocations(dataset: Dataset, scope: Scope): Allocation[] {
  const cacheKey = `${dataset.key}:${scope.id}`;
  const cached = allocationCache.get(cacheKey);
  if (cached) return cached;

  const rng = mulberry32(hash(cacheKey));
  const ranges = sortRanges(dataset.ranges);
  const allocations: Allocation[] = [];
  ranges.forEach((range, i) => {
    const usage = scope.rangeUsage[i]!;
    const used = usage.defaultUsed + usage.branchUsed;
    for (let k = 0; k < used; k++) {
      const isBranch = k >= usage.defaultUsed;
      const number = range.start + k;
      allocations.push({
        number,
        objectLabel: dataset.objectLabel(number, rng),
        objectId: `${scope.id}-${number}`,
        kind: dataset.kinds[Math.floor(rng() * dataset.kinds.length)]!,
        branch: isBranch ? BRANCHES[1 + Math.floor(rng() * (BRANCHES.length - 1))]! : "main",
        rangeId: range.id,
        source: rng() > 0.94 ? "Provided" : "Allocated",
      });
    }
  });
  allocationCache.set(cacheKey, allocations);
  return allocations;
}

export const ALL_BRANCHES = BRANCHES;
