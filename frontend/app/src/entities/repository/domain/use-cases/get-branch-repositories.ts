import { ERROR_CODES, parseCatalogueError } from "@/shared/api/errors";
import type { BranchContextParams } from "@/shared/api/types";

import {
  type BranchRepositoryNode,
  getBranchRepositoriesFromApi,
} from "@/entities/repository/api/get-branch-repositories-from-api";
import type {
  BranchRepositoriesResult,
  BranchRepository,
  BranchRepositoryListKind,
} from "@/entities/repository/domain/model/branch-repository";
import {
  GENERIC_REPOSITORY_KIND,
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

export interface GetBranchRepositoriesParams extends BranchContextParams {
  syncWithGit: boolean;
}

export type GetBranchRepositories = (
  params: GetBranchRepositoriesParams
) => Promise<BranchRepositoriesResult>;

export function getRepositoryListKind(syncWithGit: boolean): BranchRepositoryListKind {
  return syncWithGit ? GENERIC_REPOSITORY_KIND : READONLY_REPOSITORY_KIND;
}

function toBranchRepository(node: BranchRepositoryNode & { id: string }): BranchRepository {
  const kind =
    node.__typename === READONLY_REPOSITORY_KIND ? READONLY_REPOSITORY_KIND : REPOSITORY_KIND;

  return {
    id: node.id,
    kind,
    name: node.name?.value || node.display_label || node.id,
    isReadOnly: kind === READONLY_REPOSITORY_KIND,
    commit: node.commit?.value || null,
    syncStatus: {
      value: node.sync_status?.value ?? null,
      label: node.sync_status?.label ?? null,
      color: node.sync_status?.color ?? null,
      description: node.sync_status?.description ?? null,
    },
    operationalStatus: {
      value: node.operational_status?.value ?? null,
      label: node.operational_status?.label ?? null,
    },
  };
}

export const getBranchRepositories: GetBranchRepositories = async ({ branchName, syncWithGit }) => {
  const { data, errors } = await getBranchRepositoriesFromApi({
    branchName,
    kind: getRepositoryListKind(syncWithGit),
  });

  if (
    errors?.some(
      ({ extensions }) => parseCatalogueError(extensions).code === ERROR_CODES.PERMISSION_DENIED
    )
  ) {
    return { status: "denied" };
  }

  if (errors?.length || !data) {
    throw new Error(errors?.map(({ message }) => message).join("; ") || "No repositories returned");
  }

  const repositories = data.edges.flatMap((edge) =>
    edge?.node?.id ? [toBranchRepository({ ...edge.node, id: edge.node.id })] : []
  );

  return {
    status: "ok",
    repositories,
    count: data.count,
    isTruncated: data.count > repositories.length,
  };
};
