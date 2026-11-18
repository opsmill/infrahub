import {
  type CheckRemoteRefsFromApiParams,
  checkRemoteRefsFromApi,
} from "@/entities/repository/api/check-remote-refs-from-api";

export type CheckRemoteRefsParams = CheckRemoteRefsFromApiParams;

/** The id of the task that runs the check. */
export type CheckRemoteRefsResult = string;

export type CheckRemoteRefs = (params: CheckRemoteRefsParams) => Promise<CheckRemoteRefsResult>;

export const checkRemoteRefs: CheckRemoteRefs = async (params) => {
  const { data } = await checkRemoteRefsFromApi(params);
  const taskId = data?.InfrahubReadOnlyRepositoryCheckRefs?.task?.id;

  if (!taskId) {
    throw new Error("Failed to start the remote check");
  }

  return taskId;
};
