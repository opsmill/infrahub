import type { TASK_STATES } from "@/entities/tasks/domain/model/task";

export type TaskState = (typeof TASK_STATES)[number];

export type TaskListItem = {
  id: string;
  title: string;
  branch: string | null;
  state: TaskState | null;
  workflow: string | null;
  relatedNodes: { id: string; kind: string }[];
  updatedAt: string;
};

export type TaskListPage = { tasks: TaskListItem[]; count: number };
