import type { TaskState } from "@/entities/tasks/domain/model/task";

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
