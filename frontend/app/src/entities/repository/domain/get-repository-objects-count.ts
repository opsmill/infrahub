import { getRepositoryObjectsCountFromApi } from "@/entities/repository/api/get-repository-objects-count-from-api";
import { BranchContextParams } from "@/shared/api/types";

export interface GetRepositoryObjectsCountParams extends BranchContextParams {
  nodeId: string;
}

export type GetRepositoryObjectsCount = (
  params: GetRepositoryObjectsCountParams
) => Promise<number>;

export const getRepositoryObjectsCount: GetRepositoryObjectsCount = async ({
  branchName,
  nodeId,
}) => {
  const { data } = await getRepositoryObjectsCountFromApi({
    branchName,
    nodeIds: [nodeId],
  });

  return data.CoreRepositoryGroup.count;
};
