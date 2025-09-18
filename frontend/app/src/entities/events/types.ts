import type {
  ArtifactEvent,
  BranchCreatedEvent,
  BranchDeletedEvent,
  BranchMergedEvent,
  BranchRebasedEvent,
  GroupEvent,
  NodeMutatedEvent,
  StandardEvent,
} from "@/shared/api/graphql/generated/graphql";

export type EventType =
  | ArtifactEvent
  | NodeMutatedEvent
  | BranchCreatedEvent
  | BranchMergedEvent
  | BranchRebasedEvent
  | BranchDeletedEvent
  | GroupEvent
  | StandardEvent;

export type BranchEvent =
  | BranchCreatedEvent
  | BranchMergedEvent
  | BranchRebasedEvent
  | BranchDeletedEvent;
