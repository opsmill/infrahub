import type { BranchContextParams } from "@/shared/api/types";

import { getRepositoryGroupFromApi } from "@/entities/repository/api/get-repository-group-from-api";

export interface GetRepositoryGroupParams extends BranchContextParams {
  nodeId: string;
}

export type GetRepositoryGroup = (
  params: GetRepositoryGroupParams
) => Promise<{ id: string | undefined }>;

export const getRepositoryGroup: GetRepositoryGroup = async ({ branchName, nodeId }) => {
  const { data, errors } = await getRepositoryGroupFromApi({
    branchName,
    nodeIds: [nodeId],
  });

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return { id: data.CoreRepositoryGroup.edges?.[0]?.node?.id };
};
