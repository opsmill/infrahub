import type { ResultOf } from "@/shared/api/graphql/client";

import type { GET_TASK_LIST } from "@/entities/tasks/api/get-task-list-from-api";
import type { TaskListPage } from "@/entities/tasks/domain/model/task-list-item";

type TaskListConnection = ResultOf<typeof GET_TASK_LIST>["InfrahubTask"];

export function toTaskListPage(connection: TaskListConnection): TaskListPage {
  const tasks = connection.edges.flatMap(({ node }) =>
    node
      ? [
          {
            id: node.id,
            title: node.title,
            branch: node.branch ?? null,
            state: node.state ?? null,
            workflow: node.workflow ?? null,
            relatedNodes: (node.related_nodes ?? []).filter((n) => !!n),
            updatedAt: node.updated_at,
          },
        ]
      : []
  );

  return { tasks, count: connection.count };
}
