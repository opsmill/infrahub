import { toDateTime, toDateTimeOrNull } from "@/entities/repository/api/date-time.mappers";
import type { RepositoryActivityWire } from "@/entities/repository/api/get-repository-activity-from-api";
import type { RepositoryActivity } from "@/entities/repository/domain/model/repository-activity";

export function mapRepositoryActivity(wire: RepositoryActivityWire): RepositoryActivity {
  return {
    activeRuns: wire.active_runs.edges.map(({ node }) => ({
      runId: node.run_id,
      operation: node.operation,
      phase: node.phase ?? null,
      branchName: node.branch_name ?? null,
      workerId: node.worker_id,
      startedAt: toDateTime(node.started_at),
    })),
    lastRuns: wire.last_runs.edges.map(({ node }) => ({
      operation: node.operation,
      finishedAt: toDateTime(node.finished_at),
      branches: node.branches.edges.map((edge) => ({
        branchName: edge.node.branch_name,
        outcome: edge.node.outcome,
      })),
    })),
    lock: wire.lock
      ? { workerId: wire.lock.worker_id, requestedAt: toDateTimeOrNull(wire.lock.requested_at) }
      : null,
  };
}
