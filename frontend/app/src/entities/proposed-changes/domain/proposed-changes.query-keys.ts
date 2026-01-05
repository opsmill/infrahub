import { PROPOSED_CHANGES_THREAD_OBJECT } from "@/shared/config/constants";
import type { Filter } from "@/shared/hooks/useFilters";

import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";

export interface ProposedChangesListKeysParams {
  filters?: Filter[];
}

export const proposedChangesQueryKeys = {
  all: [...objectQueryKeys.all, PROPOSED_CHANGE_OBJECT] as const,
  list: ({ filters }: ProposedChangesListKeysParams) =>
    [...proposedChangesQueryKeys.all, filters] as const,
  count: ({ filters }: ProposedChangesListKeysParams) =>
    [...proposedChangesQueryKeys.all, "count", filters] as const,
  detail: (proposedChangeId: string) =>
    [...proposedChangesQueryKeys.all, proposedChangeId] as const,
  actions: (proposedChangeId: string) =>
    [...proposedChangesQueryKeys.detail(proposedChangeId), "actions"] as const,
  thread: (threadId: string) =>
    [...objectQueryKeys.all, PROPOSED_CHANGES_THREAD_OBJECT, threadId] as const,
} as const;
