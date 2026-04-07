import type {
  ArtifactEvent,
  BranchCreatedEvent,
  BranchDeletedEvent,
  BranchMergedEvent,
  BranchRebasedEvent,
  GroupEvent,
  NodeMutatedEvent,
  StandardEvent,
} from "@/shared/api/graphql/generated/types";

export type EventType = ArtifactEvent | NodeMutatedEvent | BranchEvent | GroupEvent | StandardEvent;

export type BranchEvent =
  | BranchCreatedEvent
  | BranchMergedEvent
  | BranchRebasedEvent
  | BranchDeletedEvent;
