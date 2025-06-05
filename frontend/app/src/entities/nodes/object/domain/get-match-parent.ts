import { NodeObject } from "@/entities/nodes/types";
import { ContextParams } from "@/shared/api/types";
import { getMatchParentFromApi } from "../api/get-match-parent-from-api";

export type GetMatchParentParams = ContextParams & {
  objectId: string;
};

export type GetObject = (
  params: GetMatchParentParams
) => Promise<{ id: string; node_kind: { value: string } }>;

export const getMatchParent: GetObject = async ({ branchName, atDate, objectId }) => {
  const { data } = await getMatchParentFromApi({ branchName, objectId, atDate });

  const result =
    data?.CoreNodeTriggerRule?.edges?.map((edge: { node: NodeObject }) => edge.node) ?? [];

  if (!result || result.length === 0) {
    throw new Error(`Cannot find Trigger Rule with id ${objectId}`);
  }

  return result[0];
};
