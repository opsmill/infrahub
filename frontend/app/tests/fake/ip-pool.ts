import type {
  IpAddressPoolData,
  IpPoolAllocation,
  IpPoolResource,
  IpPoolResourceUsage,
  IpPoolUtilization,
  IpPrefixPoolData,
} from "@/entities/resource-manager/domain/model/ip-pool";

export const generateIpPrefixPoolData = (
  overrides?: Partial<IpPrefixPoolData>
): IpPrefixPoolData => ({
  id: "18a3c2f1-0000-4000-8000-000000000000",
  hfid: ["PAR1 fabric links"],
  display_label: "PAR1 fabric links",
  __typename: "CoreIPPrefixPool",
  name: { value: "PAR1 fabric links" },
  description: { value: null },
  default_prefix_length: { value: 31 },
  default_prefix_type: { value: "IpamIPPrefix" },
  default_member_type: { value: "address" },
  ip_namespace: {
    id: "18a3c2f1-0000-4000-8000-0000000000ns",
    display_label: "default",
    isDefault: true,
  },
  ...overrides,
});

export const generateIpAddressPoolData = (
  overrides?: Partial<IpAddressPoolData>
): IpAddressPoolData => ({
  id: "5c0e9d12-0000-4000-8000-000000000000",
  hfid: ["Router loopbacks"],
  display_label: "Router loopbacks",
  __typename: "CoreIPAddressPool",
  name: { value: "Router loopbacks" },
  description: { value: null },
  default_prefix_length: { value: 32 },
  default_address_type: { value: "IpamIPAddress" },
  ip_namespace: {
    id: "5c0e9d12-0000-4000-8000-0000000000ns",
    display_label: "default",
    isDefault: true,
  },
  ...overrides,
});

export const generateIpPoolResourceUsage = (
  overrides?: Partial<IpPoolResourceUsage>
): IpPoolResourceUsage => ({
  utilization: 60,
  utilizationDefaultBranch: 40,
  utilizationBranches: 20,
  ...overrides,
});

export const generateIpPoolResource = (overrides?: Partial<IpPoolResource>): IpPoolResource => ({
  id: "18a3c2f1-0000-4000-8000-0000000000r1",
  __typename: "IpamIPPrefix",
  display_label: "10.10.0.0/22",
  allocationWeight: null,
  usage: generateIpPoolResourceUsage(),
  ...overrides,
});

export const generateIpPoolUtilization = (
  overrides?: Partial<IpPoolUtilization>
): IpPoolUtilization => ({
  usage: generateIpPoolResourceUsage({
    utilization: 30,
    utilizationDefaultBranch: 25,
    utilizationBranches: 5,
  }),
  resources: [
    generateIpPoolResource(),
    generateIpPoolResource({
      id: "18a3c2f1-0000-4000-8000-0000000000r2",
      display_label: "10.10.4.0/22",
      usage: generateIpPoolResourceUsage({
        utilization: 0,
        utilizationDefaultBranch: 0,
        utilizationBranches: 0,
      }),
    }),
  ],
  ...overrides,
});

export const generateIpPoolAllocation = (
  overrides?: Partial<IpPoolAllocation>
): IpPoolAllocation => ({
  id: "18a3c2f1-0000-4000-8000-0000000000a1",
  __typename: "IpamIPPrefix",
  display_label: "10.10.0.0/31",
  identifier: "par1-spine-01__par1-leaf-001__underlay",
  ...overrides,
});

export const generateIpPoolAllocations = (count: number): IpPoolAllocation[] =>
  Array.from({ length: count }, (_, index) =>
    generateIpPoolAllocation({
      id: `18a3c2f1-0000-4000-8000-${String(index).padStart(12, "0")}`,
      display_label: `10.10.${Math.floor((index * 2) / 256)}.${(index * 2) % 256}/31`,
      identifier:
        index % 7 === 3
          ? null
          : `par1-spine-0${(index % 4) + 1}__par1-leaf-${String(index + 1).padStart(3, "0")}__underlay`,
    })
  );
