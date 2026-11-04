export type PoolKind = "prefix" | "address";

export interface ResourcePrefix {
  id: string;
  prefix: string;
  weight: number;
  utilization: number;
  utilizationDefaultBranch: number;
  utilizationBranches: number;
}

export interface AllocatedRow {
  id: string;
  value: string;
  kind: string;
  identifier: string | null;
  branch: string;
}

export interface ProtoPool {
  id: string;
  poolKind: PoolKind;
  name: string;
  description: string | null;
  namespace: string;
  defaults: {
    prefixLength: number | null;
    createdKind: string | null;
    memberType: "prefix" | "address" | null;
  };
  resources: ResourcePrefix[];
  allocated: AllocatedRow[];
}

const makeRows = (
  count: number,
  valueAt: (index: number) => string,
  kind: string,
  identifierAt: (index: number) => string | null
): AllocatedRow[] =>
  Array.from({ length: count }, (_, index) => ({
    id: `row-${index}`,
    value: valueAt(index),
    kind,
    identifier: identifierAt(index),
    branch: "main",
  }));

export const PREFIX_POOL: ProtoPool = {
  id: "18a3c2f1-7b4e-4d2a-9c61-3e5f0a2b8d47",
  poolKind: "prefix",
  name: "PAR1 fabric point-to-point links (spine and leaf underlay, phase 2 expansion)",
  description:
    "Allocates the /31 links between spines and leaves in the Paris PAR1 data center. Generators reserve each link with the device pair as identifier.",
  namespace: "default",
  defaults: { prefixLength: 31, createdKind: "IpamIPPrefix", memberType: "address" },
  resources: [
    { id: "r1", prefix: "10.10.0.0/22", weight: 100, utilization: 91, utilizationDefaultBranch: 84, utilizationBranches: 7 },
    { id: "r2", prefix: "10.10.4.0/22", weight: 100, utilization: 38, utilizationDefaultBranch: 38, utilizationBranches: 0 },
    { id: "r3", prefix: "10.10.8.0/23", weight: 50, utilization: 4.2, utilizationDefaultBranch: 0, utilizationBranches: 4.2 },
    { id: "r4", prefix: "2001:db8:a10:ff00::/56", weight: 10, utilization: 0, utilizationDefaultBranch: 0, utilizationBranches: 0 },
  ],
  allocated: makeRows(
    42,
    (index) => `10.10.${Math.floor((index * 2) / 256)}.${(index * 2) % 256}/31`,
    "IpamIPPrefix",
    (index) =>
      index % 7 === 3 ? null : `par1-spine-0${(index % 4) + 1}__par1-leaf-${String(index + 1).padStart(3, "0")}__underlay`
  ),
};

export const ADDRESS_POOL: ProtoPool = {
  id: "5c0e9d12-2a7f-4b3e-8f14-6d9a1c3b2e70",
  poolKind: "address",
  name: "Router loopbacks",
  description: null,
  namespace: "default",
  defaults: { prefixLength: 32, createdKind: "IpamIPAddress", memberType: null },
  resources: [
    { id: "r1", prefix: "10.255.0.0/24", weight: 100, utilization: 62, utilizationDefaultBranch: 60, utilizationBranches: 2 },
    { id: "r2", prefix: "10.255.1.0/24", weight: 100, utilization: 0, utilizationDefaultBranch: 0, utilizationBranches: 0 },
  ],
  allocated: makeRows(
    40,
    (index) => `10.255.0.${index + 1}/32`,
    "IpamIPAddress",
    (index) => (index % 5 === 0 ? null : `DcimDevice__par1-rtr-${String(index + 1).padStart(2, "0")}__primary_address`)
  ),
};

export const UNSET_POOL: ProtoPool = {
  id: "a71b4e3d-0c9f-42d8-b5e6-1f2a3c4d5e6f",
  poolKind: "prefix",
  name: "Customer VRF subnets",
  description: "Every request sets its own prefix length.",
  namespace: "customer-blue-shared-services-vrf-europe-west",
  defaults: { prefixLength: null, createdKind: null, memberType: "prefix" },
  resources: [
    { id: "r1", prefix: "172.16.0.0/12", weight: 100, utilization: 12, utilizationDefaultBranch: 12, utilizationBranches: 0 },
  ],
  allocated: makeRows(
    6,
    (index) => `172.16.${index * 4}.0/22`,
    "IpamIPPrefix",
    () => null
  ),
};

export const DATASETS = [
  { id: "prefix", label: "Prefix pool", pool: PREFIX_POOL },
  { id: "address", label: "Address pool", pool: ADDRESS_POOL },
  { id: "unset", label: "Unset defaults", pool: UNSET_POOL },
] as const;
