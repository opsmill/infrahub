import {
  type CheckRemoteRefsFromApiParams,
  checkRemoteRefsFromApi,
} from "@/entities/repository/api/check-remote-refs-from-api";

export type CheckRemoteRefsParams = CheckRemoteRefsFromApiParams;

export type CheckRemoteRefs = (params: CheckRemoteRefsParams) => Promise<string>;

export const checkRemoteRefs: CheckRemoteRefs = async (params) => {
  const { data } = await checkRemoteRefsFromApi(params);
  const taskId = data?.InfrahubReadOnlyRepositoryCheckRefs?.task?.id;

  if (!taskId) {
    throw new Error("Failed to start the remote check");
  }

  return taskId;
};
