import type { BranchStatus } from "@/shared/api/graphql/generated/types";
import type { Filter } from "@/shared/hooks/useFilters";

export const getNameFilterValue = (filters?: Filter[]) => {
  const nameFilter = filters?.find((f) => f.name === "any__value");
  return nameFilter?.value as string | undefined;
};

export const getStatusFilterValue = (filters?: Filter[]): BranchStatus | undefined => {
  const statusFilter = filters?.find((f) => f.name === "status__value");
  return statusFilter?.value as BranchStatus | undefined;
};

export const getCreatedByFilterValue = (filters?: Filter[]) => {
  const createdByFilter = filters?.find((f) => f.name === "node_metadata__created_by__ids");
  if (!createdByFilter?.value) return;

  const relationships = createdByFilter.value as Array<{ id: string }>;
  // Return first ID since backend expects single ID, not array
  return relationships[0]?.id;
};

export const getDateFilterValue = (filters?: Filter[], fieldName?: string, condition?: string) => {
  const filter = filters?.find((f) => f.name === `${fieldName}__${condition}`);
  return filter?.value as string | undefined;
};

export const getBranchDateFilters = (filters?: Filter[]) => {
  return {
    branchedFromAfter: getDateFilterValue(filters, "branched_from", "after"),
    branchedFromBefore: getDateFilterValue(filters, "branched_from", "before"),
    createdAtAfter: getDateFilterValue(filters, "node_metadata__created_at", "after"),
    createdAtBefore: getDateFilterValue(filters, "node_metadata__created_at", "before"),
    updatedAtAfter: getDateFilterValue(filters, "node_metadata__updated_at", "after"),
    updatedAtBefore: getDateFilterValue(filters, "node_metadata__updated_at", "before"),
  };
};
