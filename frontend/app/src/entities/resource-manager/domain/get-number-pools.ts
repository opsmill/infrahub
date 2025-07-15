import {
  GetNumberPoolsFromApiParams,
  getNumberPoolsFromApi,
} from "@/entities/resource-manager/api/get-number-pools-from-api";
import { NUMBER_POOL_KIND } from "@/entities/resource-manager/constants";

export type GetNumberPoolsParams = GetNumberPoolsFromApiParams;

export type NumberPool = {
  id: string;
  label: string;
  kind: string;
  nodeAttribute: {
    id: string;
    name: string;
  };
};

export type GetNumberPools = (params: GetNumberPoolsParams) => Promise<Array<NumberPool>>;

export const getNumberPools: GetNumberPools = async (params) => {
  const { data, errors } = await getNumberPoolsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data[NUMBER_POOL_KIND].edges.map(({ node }: any) => ({
    id: node.id,
    label: node.display_label,
    kind: node.__typename,
    nodeAttribute: {
      id: node.node_attribute.id,
      name: node.node_attribute.value,
    },
  }));
};
