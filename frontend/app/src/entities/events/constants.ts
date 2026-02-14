export const INFRAHUB_EVENT = "InfrahubEvent";

export const EVENT_TYPE_CHOICES = [
  {
    label: "Artifact created",
    name: "infrahub.artifact.created",
  },
  {
    label: "Artifact updated",
    name: "infrahub.artifact.updated",
  },
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
  {
    label: "Validator failed",
    name: "infrahub.validator.failed",
  },
  {
    label: "Validator passed",
    name: "infrahub.validator.passed",
  },
  {
    label: "Validator started",
    name: "infrahub.validator.started",
  },
];
