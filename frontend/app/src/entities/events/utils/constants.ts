export const NODE_MUTATED_EVENT = "NodeMutatedEvent";
export const BRANCH_DELETED_EVENT = "BranchDeletedEvent";
export const BRANCH_CREATED_EVENT = "BranchCreatedEvent";
export const BRANCH_REBASEDED_EVENT = "BranchRebasedEvent";
export const GROUP_DELETED_EVENT = "GroupDeletedEvent";
export const GROUP_CREATED_EVENT = "GroupCreatedEvent";
export const GROUP_REBASEDED_EVENT = "GroupRebasedEvent";
export const STANDARD_EVENT = "StandardEvent";

export const INFRAHUB_EVENT = "InfrahubEvent";

export const BRANCH_EVENTS = [BRANCH_DELETED_EVENT, BRANCH_CREATED_EVENT, BRANCH_REBASEDED_EVENT];

export const STANDARD_EVENTS = [STANDARD_EVENT];

export const EVENT_TYPE_CHOICES = [
  {
    label: "Node created",
    name: "infrahub.node.created",
  },
  {
    label: "Node updated",
    name: "infrahub.node.updated",
  },
  {
    label: "Node deleted",
    name: "infrahub.node.deleted",
  },
  {
    label: "Branch created",
    name: "infrahub.branch.created",
  },
  {
    label: "Branch rebased",
    name: "infrahub.branch.rebased",
  },
  {
    label: "Branch merged",
    name: "infrahub.branch.merged",
  },
  {
    label: "Branch deleted",
    name: "infrahub.branch.deleted",
  },
  {
    label: "Added to group",
    name: "infrahub.group.member_added",
  },
  {
    label: "Removed from group",
    name: "infrahub.group.member_removed",
  },
  {
    label: "Schema updated",
    name: "infrahub.schema.updated",
  },
  {
    label: "Commit updated",
    name: "infrahub.repository.update_commit",
  },
]