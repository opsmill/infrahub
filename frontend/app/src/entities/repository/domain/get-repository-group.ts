import { getRepositoryGroupFromApi } from "@/entities/repository/api/get-repository-group-from-api";
import { BranchContextParams } from "@/shared/api/types";

export interface GetRepositoryGroupParams extends BranchContextParams {
  nodeId: string;
}

export type GetRepositoryGroup = (params: GetRepositoryGroupParams) => Promise<number>;

export const getRepositoryGroup: GetRepositoryGroup = async ({ branchName, nodeId }) => {
  const { data } = await getRepositoryGroupFromApi({
    branchName,
    nodeIds: [nodeId],
  });

  return data.CoreRepositoryGroup.edges?.[0]?.node?.id;
};
