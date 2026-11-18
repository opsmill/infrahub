import type {
  AccountLoggedInEventType,
  AccountLoggedOutEventType,
  ArtifactEvent,
  BranchCreatedEvent,
  BranchDeletedEvent,
  BranchMergedEvent,
  BranchRebasedEvent,
  EventNodeInterface,
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

// The events query selects only these shared event fields for proposed change events.
type CommonEventFields<T extends EventNodeInterface & { __typename: string }> = Pick<
  T,
  | "__typename"
  | "id"
  | "event"
  | "branch"
  | "occurred_at"
  | "level"
  | "account_id"
  | "primary_node"
  | "related_nodes"
  | "has_children"
>;

export type ProposedChangeEvent =
  | CommonEventFields<ProposedChangeApprovalsRevokedEvent>
  | CommonEventFields<ProposedChangeMergedEvent>
  | CommonEventFields<ProposedChangeReviewEvent>
  | CommonEventFields<ProposedChangeReviewRequestedEvent>
  | CommonEventFields<ProposedChangeReviewRevokedEvent>
  | CommonEventFields<ProposedChangeThreadEvent>;

export type EventType =
  | AccountEvent
  | BranchEvent
  | ArtifactEvent
  | NodeMutatedEvent
  | GroupEvent
  | GroupAutoCreateEvent
  | ProposedChangeEvent
  | StandardEvent;
