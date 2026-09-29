// PROTOTYPE — the task rows are mocked, but their links must open a real task details page.
// Each mocked row borrows the id of a real task on this instance with the same kind of workflow,
// preferring the same state, and never two rows on one task when enough tasks exist. The task
// manager caps a page at 200.
import { useQuery } from "@tanstack/react-query";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";

import type { ProtoData, TaskRow } from "./data";

type RealTask = { id: string; state: string; workflow: string | null };

const WORKFLOW: Record<TaskRow["workflow"], RegExp> = {
  Import: /git-repository|import/i,
  Generator: /generator/i,
  Artifacts: /artifact/i,
  Validate: /validate/i,
  Rebase: /rebase/i,
};

function useRealTasks() {
  return useQuery({
    queryKey: ["proto-branch-details", "real-task-ids"],
    queryFn: async () => {
      const { data } = await graphqlClient.query<{
        InfrahubTask: { edges: { node: RealTask }[] };
      }>({
        query: graphql(
          jsonToGraphQLQuery({
            query: {
              InfrahubTask: {
                __args: { limit: 200 },
                edges: { node: { id: true, state: true, workflow: true } },
              },
            },
          })
        ),
      });
      return data?.InfrahubTask.edges.map((e) => e.node) ?? [];
    },
    staleTime: Number.POSITIVE_INFINITY,
  });
}

function assign(tasks: TaskRow[], real: RealTask[]) {
  const used = new Set<string>();
  const ids = new Map<string, string>();
  for (const t of tasks) {
    const sameKind = real.filter((r) => WORKFLOW[t.workflow].test(r.workflow ?? ""));
    const pick =
      [
        sameKind.filter((r) => r.state === t.state),
        sameKind,
        real.filter((r) => r.state === t.state),
        real,
      ]
        .map((pool) => pool.find((r) => !used.has(r.id)))
        .find(Boolean) ??
      sameKind[0] ??
      real[0];
    if (!pick) continue;
    used.add(pick.id);
    ids.set(t.id, pick.id);
  }
  return ids;
}

/** Same data, with every task reference (rows, error bands, generator runs) on a real task id. */
export function useWithRealTaskIds(data: ProtoData): ProtoData {
  const { data: real = [] } = useRealTasks();
  if (!real.length) return data;

  const ids = assign(data.tasks, real);
  const to = (id: string) => ids.get(id) ?? id;
  return {
    ...data,
    tasks: data.tasks.map((t) => ({ ...t, id: to(t.id) })),
    repos: data.repos.map((r) => ({
      ...r,
      importError: r.importError && { ...r.importError, taskId: to(r.importError.taskId) },
      generators: r.generators.map((g) => ({ ...g, taskId: to(g.taskId) })),
    })),
  };
}
