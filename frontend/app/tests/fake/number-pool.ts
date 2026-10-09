import type {
  NumberPoolAllocation,
  NumberPoolData,
  NumberPoolRange,
  NumberPoolUsage,
  NumberPoolUtilization,
} from "@/entities/resource-manager/domain/model/number-pool";

export const generateNumberPoolData = (overrides?: Partial<NumberPoolData>): NumberPoolData => ({
  id: "c03b91de-0000-4000-8000-000000000000",
  hfid: ["Interface speeds"],
  display_label: "Interface speeds",
  __typename: "CoreNumberPool",
  name: { value: "Interface speeds" },
  description: { value: null },
  pool_type: { value: "User" },
  node: { value: "InfraInterface" },
  node_attribute: { value: "speed" },
  allocation_scope: { value: [] },
  ...overrides,
});

export const generateNumberPoolUsage = (overrides?: Partial<NumberPoolUsage>): NumberPoolUsage => ({
  size: 50,
  used: 30,
  usedDefaultBranch: 28,
  usedBranches: 2,
  utilization: 60,
  ...overrides,
});

export const generateNumberPoolRange = (overrides?: Partial<NumberPoolRange>): NumberPoolRange => ({
  id: "c03b91de-0000-4000-8000-0000000000a1",
  __typename: "CoreNumberPoolRange",
  start: { value: 1 },
  end: { value: 50 },
  allocation_weight: { value: 10 },
  usage: generateNumberPoolUsage(),
  ...overrides,
});

export const generateNumberPoolUtilization = (
  overrides?: Partial<NumberPoolUtilization>
): NumberPoolUtilization => ({
  usage: generateNumberPoolUsage({ size: 100, used: 30, utilization: 30 }),
  ranges: [
    generateNumberPoolRange(),
    generateNumberPoolRange({
      id: "c03b91de-0000-4000-8000-0000000000a2",
      start: { value: 51 },
      end: { value: 100 },
      allocation_weight: { value: 0 },
      usage: generateNumberPoolUsage({
        used: 0,
        usedDefaultBranch: 0,
        usedBranches: 0,
        utilization: 0,
      }),
    }),
  ],
  ...overrides,
});

export const generateNumberPoolAllocation = (
  overrides?: Partial<NumberPoolAllocation>
): NumberPoolAllocation => ({
  value: 1,
  branch: "main",
  holder: {
    id: "c03b91de-0000-4000-8000-0000000000d1",
    __typename: "InfraInterface",
    display_label: "ethernet1",
  },
  provenance: "ALLOCATED",
  rangeId: "c03b91de-0000-4000-8000-0000000000a1",
  ...overrides,
});
