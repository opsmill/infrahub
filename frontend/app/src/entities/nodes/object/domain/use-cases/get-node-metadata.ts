import {
  type GetNodeMetadataFromApiParams,
  getNodeMetadataFromApi,
} from "@/entities/nodes/object/api/get-node-metadata-from-api";
import type { NodeMetadata } from "@/entities/nodes/types";

export type GetNodeMetadataParams = GetNodeMetadataFromApiParams;

export type GetNodeMetadata = (params: GetNodeMetadataParams) => Promise<NodeMetadata>;

export const getNodeMetadata: GetNodeMetadata = async ({
  objectId,
  objectKind,
  branchName,
  atDate,
}) => {
  const { data, errors } = await getNodeMetadataFromApi({
    objectId,
    objectKind,
    branchName,
    atDate,
  });

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const nodeMetadata = data[objectKind]?.edges?.[0]?.node_metadata;

  if (!nodeMetadata) {
    throw new Error("Node metadata not found");
  }

  return nodeMetadata;
};
