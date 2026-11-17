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
  ProposedChangeApprovalsRevokedEvent,
  ProposedChangeMergedEvent,
  ProposedChangeReviewEvent,
  ProposedChangeReviewRequestedEvent,
  ProposedChangeReviewRevokedEvent,
  ProposedChangeThreadEvent,
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

export type ProposedChangeEvent =
  | ProposedChangeApprovalsRevokedEvent
  | ProposedChangeMergedEvent
  | ProposedChangeReviewEvent
  | ProposedChangeReviewRequestedEvent
  | ProposedChangeReviewRevokedEvent
  | ProposedChangeThreadEvent;

export type EventType =
  | AccountEvent
  | BranchEvent
  | ArtifactEvent
  | NodeMutatedEvent
  | GroupEvent
  | GroupAutoCreateEvent
  | ProposedChangeEvent
  | StandardEvent;
