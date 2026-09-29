import type { TASK_STATES } from "@/entities/tasks/domain/model/task";

export type TaskState = (typeof TASK_STATES)[number];

export type BranchTask = {
  id: string;
  title: string;
  state: TaskState | null;
  workflow: string | null;
  relatedNodes: { id: string; kind: string }[];
  updatedAt: string;
};

export type BranchTasksPage = { tasks: BranchTask[]; count: number };
