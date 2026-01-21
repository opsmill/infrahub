import {
  type ReimportLastCommitFromApiParams,
  reimportLastCommitFromApi,
} from "@/entities/repository/api/reimport-last-commit-from-api";

export type ReimportLastCommitParams = ReimportLastCommitFromApiParams;

export interface ReimportLastCommitResult {
  ok: boolean;
  taskId?: string;
}

export type ReimportLastCommit = (
  params: ReimportLastCommitParams
) => Promise<ReimportLastCommitResult>;

export const reimportLastCommit: ReimportLastCommit = async (params) => {
  const { data, errors } = await reimportLastCommitFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (!data?.InfrahubReadOnlyRepositoryImportLastCommit) {
    throw new Error("Failed to start import from remote");
  }

  const result = data.InfrahubReadOnlyRepositoryImportLastCommit;

  return {
    ok: result.ok,
    taskId: result.task?.id,
  };
};
