export const TASK_OBJECT = "InfrahubTask";
export const TASK_TARGET = "CoreTaskTarget";

export const TASK_STATE_COMPLETED = "COMPLETED" as const;
export const TASK_STATE_RUNNING = "RUNNING" as const;
export const TASK_STATE_PENDING = "PENDING" as const;
export const TASK_STATE_FAILED = "FAILED" as const;

export const TASK_STATE_SCHEDULED = "SCHEDULED" as const;
export const TASK_STATE_CANCELING = "CANCELLING" as const;
export const TASK_STATE_CANCELLED = "CANCELLED" as const;
export const TASK_STATE_CRASHED = "CRASHED" as const;
export const TASK_STATE_PAUSED = "PAUSED" as const;

export const TASK_STATES = [
  TASK_STATE_SCHEDULED,
  TASK_STATE_PENDING,
  TASK_STATE_RUNNING,
  TASK_STATE_COMPLETED,
  TASK_STATE_FAILED,
  TASK_STATE_CANCELLED,
  TASK_STATE_CRASHED,
  TASK_STATE_PAUSED,
  TASK_STATE_CANCELING,
];

export const TASK_ONGOING_STATES = [
  TASK_STATE_SCHEDULED,
  TASK_STATE_PENDING,
  TASK_STATE_RUNNING,
  TASK_STATE_CANCELING,
];

export const MORE_TASKS_STATES = [
  TASK_STATE_SCHEDULED,
  TASK_STATE_CANCELING,
  TASK_STATE_CANCELLED,
  TASK_STATE_CRASHED,
  TASK_STATE_PAUSED,
];

export const WORKFLOW_TYPE_CORE = "CORE" as const;
export const WORKFLOW_TYPE_USER = "USER" as const;
export const WORKFLOW_TYPE_INTERNAL = "INTERNAL" as const;

export const WORKFLOW_TYPES = [
  WORKFLOW_TYPE_CORE,
  WORKFLOW_TYPE_USER,
  WORKFLOW_TYPE_INTERNAL,
] as const;

// The single mapping from API enum value to operator-facing label, so the two cannot drift.
export const WORKFLOW_TYPE_LABELS: Record<(typeof WORKFLOW_TYPES)[number], string> = {
  [WORKFLOW_TYPE_CORE]: "Core",
  [WORKFLOW_TYPE_USER]: "User",
  [WORKFLOW_TYPE_INTERNAL]: "System",
};

export const BRANCH_VALIDATE_WORKFLOW = "branch-validate";
export const BRANCH_REBASE_WORKFLOW = "branch-rebase";
export const BRANCH_MERGE_WORKFLOW = "merge-branch-mutation";
export const PROPOSED_CHANGE_MERGE_WORKFLOW = "proposed-change-merge";
