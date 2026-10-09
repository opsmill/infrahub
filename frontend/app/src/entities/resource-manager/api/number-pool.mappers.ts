import type { NumberPoolNode } from "@/entities/resource-manager/api/get-number-pool-from-api";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_KIND,
  NUMBER_POOL_TYPE_SCHEMA,
  NUMBER_POOL_TYPE_USER,
} from "@/entities/resource-manager/domain/model/pool";

const isFieldNameList = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

export const mapToNumberPoolData = (node: NumberPoolNode): NumberPoolData => {
  const allocationScope = node.allocation_scope?.value;

  return {
    id: node.id,
    hfid: node.hfid,
    display_label: node.display_label,
    __typename: NUMBER_POOL_KIND,
    name: { value: node.name?.value ?? "" },
    description: { value: node.description?.value || null },
    pool_type: {
      value:
        node.pool_type?.value === NUMBER_POOL_TYPE_SCHEMA
          ? NUMBER_POOL_TYPE_SCHEMA
          : NUMBER_POOL_TYPE_USER,
    },
    node: { value: node.node?.value ?? "" },
    node_attribute: { value: node.node_attribute?.value ?? "" },
    allocation_scope: { value: isFieldNameList(allocationScope) ? allocationScope : [] },
  };
};
