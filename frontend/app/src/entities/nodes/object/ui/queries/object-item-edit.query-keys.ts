import type { ContextParams } from "@/shared/api/types";

interface ObjectItemEditDetailParams extends ContextParams {
  objectKind: string;
  objectId: string;
  extraRelationshipNames?: string[];
}

export const objectItemEditQueryKeys = {
  all: ["object-item-edit"] as const,
  allWithContext: ({ branchName, atDate }: ContextParams) =>
    [...objectItemEditQueryKeys.all, branchName, atDate] as const,
  detail: ({
    objectKind,
    objectId,
    extraRelationshipNames,
    ...context
  }: ObjectItemEditDetailParams) =>
    [
      ...objectItemEditQueryKeys.allWithContext(context),
      objectKind,
      objectId,
      extraRelationshipNames,
    ] as const,
};
