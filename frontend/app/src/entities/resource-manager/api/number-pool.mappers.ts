import type { NumberPoolNode } from "@/entities/resource-manager/api/get-number-pool-from-api";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_KIND,
  NUMBER_POOL_TYPE_SCHEMA,
  NUMBER_POOL_TYPE_USER,
} from "@/entities/resource-manager/domain/model/pool";

export const mapToNumberPoolData = (node: NumberPoolNode): NumberPoolData => {
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
    allocation_scope: {
      value:
        (
          node.allocation_scope?.value as Array<{
            id: string;
            name: string;
          }> | null
        )?.map(({ name }) => name) ?? [],
    },
    ranges: (node.ranges?.edges ?? []).flatMap(({ node: range }) =>
      range?.start?.value == null || range.end?.value == null
        ? []
        : [
            {
              start: range.start.value,
              end: range.end.value,
              allocation_weight: range.allocation_weight?.value ?? null,
            },
          ]
    ),
  };
};
