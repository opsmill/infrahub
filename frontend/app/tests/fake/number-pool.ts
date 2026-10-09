import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";

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
