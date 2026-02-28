export interface GroupsKeysParams {
  objectKind: string;
  objectId: string;
  branchName: string;
  atDate?: Date | null;
}

export const groupsQueryKeys = {
  all: ["groups"] as const,
  list: (params: GroupsKeysParams) =>
    [
      ...groupsQueryKeys.all,
      "list",
      params.objectKind,
      params.objectId,
      params.branchName,
      params.atDate,
    ] as const,
};
