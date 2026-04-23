import { graphql } from "gql.tada";
import { useQuery } from "@tanstack/react-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// Scoped subset of the TASK_DETAILS query used by the main tasks UI. We don't
// need logs or related-nodes here — the drawer just maps (state, progress) to
// the InstallDrawerState machine.
const INSTALL_TASK_STATUS = graphql(`
  query INSTALL_TASK_STATUS($ids: [String]) {
    InfrahubTask(ids: $ids) {
      count
      edges {
        node {
          id
          state
          progress
        }
      }
    }
  }
`);

export type InstallTaskState =
  | "SCHEDULED"
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "CRASHED"
  | "PAUSED"
  | null;

export interface InstallTaskSnapshot {
  state: InstallTaskState;
  progress: number | null;
  found: boolean;
}

async function fetchInstallTaskStatus(taskId: string): Promise<InstallTaskSnapshot> {
  const { data } = await graphqlClient.query({
    query: INSTALL_TASK_STATUS,
    variables: { ids: [taskId] },
    fetchPolicy: "no-cache",
  });
  const node = data?.InfrahubTask?.edges?.[0]?.node;
  if (!node) {
    return { state: null, progress: null, found: false };
  }
  return {
    state: (node.state ?? null) as InstallTaskState,
    progress: typeof node.progress === "number" ? node.progress : null,
    found: true,
  };
}

/**
 * Polls the `InfrahubTask` GraphQL endpoint for a single task, returning a
 * state snapshot the install drawer maps to its InstallDrawerState machine.
 *
 * Polls every 3s while the task is still in flight. Once the server reports a
 * terminal state (or reports "not found" after a grace window — the task may
 * still be a Prefect-only entity, but the UI has no further signal), polling
 * stops.
 */
export function useInstallTaskStatus(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["schema-marketplace", "task-status", taskId],
    queryFn: () => fetchInstallTaskStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const snapshot = query.state.data;
      if (!snapshot) return 3_000;
      if (!snapshot.found) return 3_000;
      if (snapshot.state && ["COMPLETED", "FAILED", "CANCELLED", "CRASHED"].includes(snapshot.state)) {
        return false;
      }
      return 3_000;
    },
    refetchOnWindowFocus: false,
  });
}
