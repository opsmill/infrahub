import {
  EventNodeInterface,
  GroupEvent,
  NodeMutatedEvent,
} from "@/shared/api/graphql/generated/graphql";
import {
  BRANCH_CREATED_EVENT,
  BRANCH_DELETED_EVENT,
  BRANCH_REBASEDED_EVENT,
  NODE_MUTATED_EVENT,
} from "@/entities/events/constants";

export type BranchEventType = EventNodeInterface & {
  __typename:
    | typeof BRANCH_DELETED_EVENT
    | typeof BRANCH_CREATED_EVENT
    | typeof BRANCH_REBASEDED_EVENT;
};

export type NodeEventType = NodeMutatedEvent & {
  __typename: typeof NODE_MUTATED_EVENT;
};

export type EventType = BranchEventType | NodeEventType | GroupEvent;
