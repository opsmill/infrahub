import { deleteBranchFromApi } from "@/entities/branches/api/delete-branch-from-api";

export type DeleteBranchesFromApiParams = {
  names: string[];
};

export type DeleteBranchesFromApiResult = {
  deleted: string[];
  failed: string[];
};

export async function deleteBranchesFromApi(
  params: DeleteBranchesFromApiParams
): Promise<DeleteBranchesFromApiResult> {
  const results = await Promise.allSettled(
    params.names.map((name) => deleteBranchFromApi({ name }))
  );

  return params.names.reduce<DeleteBranchesFromApiResult>(
    (acc, name, index) => {
      const result = results[index];
      const isSuccess = result?.status === "fulfilled" && result.value.data?.BranchDelete?.ok;
      return {
        deleted: isSuccess ? [...acc.deleted, name] : acc.deleted,
        failed: isSuccess ? acc.failed : [...acc.failed, name],
      };
    },
    { deleted: [], failed: [] }
  );
}
