import { PROPOSED_CHANGES_THREAD_OBJECT } from "@/config/constants";

import {
  getProposedChangeThreadFromApi,
  type ProposedChangeThreadFromApiParams,
} from "@/entities/proposed-changes/api/get-proposed-change-thread-from-api";

export type GetProposedChangeThreadParams = ProposedChangeThreadFromApiParams;

export type GetProposedChangeThread = (params: GetProposedChangeThreadParams) => Promise<any>;

export const getProposedChangeThread: GetProposedChangeThread = async (params) => {
  const { data, errors } = await getProposedChangeThreadFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const edges = data?.[PROPOSED_CHANGES_THREAD_OBJECT]?.edges;

  if (!edges?.length) {
    throw new Error("No thread data found");
  }

  return edges[0].node;
};
