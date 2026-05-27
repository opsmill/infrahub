import type {
  AccountLoggedInEventType,
  AccountLoggedOutEventType,
  ArtifactEvent,
  BranchCreatedEvent,
  BranchDeletedEvent,
  BranchMergedEvent,
  BranchRebasedEvent,
  GroupAutoCreateCappedEventType,
  GroupAutoCreatedEventType,
  GroupAutoCreateRejectedEventType,
  GroupEvent,
  NodeMutatedEvent,
  StandardEvent,
} from "@/shared/api/graphql/generated/types";

export type AccountEvent = AccountLoggedInEventType | AccountLoggedOutEventType;

export type BranchEvent =
  | BranchCreatedEvent
  | BranchMergedEvent
  | BranchRebasedEvent
  | BranchDeletedEvent;

export type GroupAutoCreateEvent =
  | GroupAutoCreatedEventType
  | GroupAutoCreateRejectedEventType
  | GroupAutoCreateCappedEventType;

export type EventType =
  | AccountEvent
  | BranchEvent
  | ArtifactEvent
  | NodeMutatedEvent
  | GroupEvent
  | GroupAutoCreateEvent
  | StandardEvent;
