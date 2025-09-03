import { PROPOSED_CHANGES_THREAD_OBJECT } from "@/config/constants";
import {
  ProposedChangeThreadFromApiParams,
  getProposedChangeThreadFromApi,
} from "../api/get-proposed-change-thread-from-api";

export type GetProposedChangeThreadParams = ProposedChangeThreadFromApiParams;

export type GetProposedChangeThread = (params: GetProposedChangeThreadParams) => Promise<any>;

export const getProposedChangeThread: GetProposedChangeThread = async (
  params: ProposedChangeThreadFromApiParams
) => {
  const { data, errors } = await getProposedChangeThreadFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const edges = data?.[PROPOSED_CHANGES_THREAD_OBJECT]?.edges;

  if (!edges?.length) {
    throw new Error("No thread data found");
  }

  return edges[0].node;
};
