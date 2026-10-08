import {
  type CheckRemoteRefsFromApiParams,
  checkRemoteRefsFromApi,
} from "@/entities/repository/api/check-remote-refs-from-api";

export type CheckRemoteRefsParams = CheckRemoteRefsFromApiParams;

export interface CheckRemoteRefsResult {
  ok: boolean;
  taskId?: string;
}

export type CheckRemoteRefs = (params: CheckRemoteRefsParams) => Promise<CheckRemoteRefsResult>;

export const checkRemoteRefs: CheckRemoteRefs = async (params) => {
  const { data, errors } = await checkRemoteRefsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (!data?.InfrahubReadOnlyRepositoryCheckRefs) {
    throw new Error("Failed to start the remote check");
  }

  const result = data.InfrahubReadOnlyRepositoryCheckRefs;

  return {
    ok: result.ok ?? false,
    taskId: result.task?.id ?? undefined,
  };
};
