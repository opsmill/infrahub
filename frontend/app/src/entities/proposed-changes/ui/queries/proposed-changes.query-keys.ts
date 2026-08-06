import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import { PROPOSED_CHANGES_THREAD_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change-thread";

export interface ProposedChangesListKeysParams {
  filters?: Filter[];
  sort?: Sort[];
}

export const proposedChangesQueryKeys = {
  all: [...objectQueryKeys.all, PROPOSED_CHANGE_OBJECT] as const,
  list: ({ filters, sort }: ProposedChangesListKeysParams) =>
    [...proposedChangesQueryKeys.all, filters, sort] as const,
  count: ({ filters }: ProposedChangesListKeysParams) =>
    [...proposedChangesQueryKeys.all, "count", filters] as const,
  detail: (proposedChangeId: string) =>
    [...proposedChangesQueryKeys.all, proposedChangeId] as const,
  actions: (proposedChangeId: string) =>
    [...proposedChangesQueryKeys.detail(proposedChangeId), "actions"] as const,
  thread: (threadId: string) =>
    [...objectQueryKeys.all, PROPOSED_CHANGES_THREAD_OBJECT, threadId] as const,
} as const;
