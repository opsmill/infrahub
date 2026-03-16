import {
  type ImportCurrentCommitFromApiParams,
  importCurrentCommitFromApi,
} from "@/entities/repository/api/import-current-commit-from-api";

export type ImportCurrentCommitParams = ImportCurrentCommitFromApiParams;

export interface ImportCurrentCommitResult {
  ok: boolean;
  taskId?: string;
}

export type ImportCurrentCommit = (
  params: ImportCurrentCommitParams
) => Promise<ImportCurrentCommitResult>;

export const importCurrentCommit: ImportCurrentCommit = async (params) => {
  const { data, errors } = await importCurrentCommitFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (!data?.InfrahubRepositoryProcess) {
    throw new Error("Failed to start import of current commit");
  }

  const result = data.InfrahubRepositoryProcess;

  return {
    ok: result.ok ?? false,
    taskId: result.task?.id ?? undefined,
  };
};
