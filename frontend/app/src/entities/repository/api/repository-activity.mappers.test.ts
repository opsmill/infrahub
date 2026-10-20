import { describe, expect, it } from "vitest";

import type { RepositoryActivityWire } from "@/entities/repository/api/get-repository-activity-from-api";
import { mapRepositoryActivity } from "@/entities/repository/api/repository-activity.mappers";

const WIRE = {
  repository_id: "repository-1",
  active_runs: {
    edges: [
      {
        node: {
          run_id: "run-1",
          operation: "SYNC",
          phase: null,
          branch_name: null,
          worker_id: "worker-1",
          started_at: "2026-10-14T14:00:00Z",
          updated_at: "2026-10-14T14:00:30Z",
        },
      },
    ],
  },
  last_runs: {
    edges: [
      {
        node: {
          operation: "MERGE",
          started_at: "2026-10-14T13:00:00Z",
          finished_at: "2026-10-14T13:01:00Z",
          branches: { edges: [{ node: { branch_name: "main", outcome: "IMPORTED" } }] },
        },
      },
    ],
  },
  lock: { worker_id: "worker-1", requested_at: null },
} as RepositoryActivityWire;

describe("mapRepositoryActivity", () => {
  it("flattens both lists and keeps a lock whose request time cannot be read", () => {
    expect(mapRepositoryActivity(WIRE)).toEqual({
      activeRuns: [
        {
          runId: "run-1",
          operation: "SYNC",
          phase: null,
          branchName: null,
          workerId: "worker-1",
          startedAt: "2026-10-14T14:00:00Z",
        },
      ],
      lastRuns: [
        {
          operation: "MERGE",
          finishedAt: "2026-10-14T13:01:00Z",
          branches: [{ branchName: "main", outcome: "IMPORTED" }],
        },
      ],
      lock: { workerId: "worker-1", requestedAt: null },
    });
  });

  it("reports no lock when the lock is not held", () => {
    expect(mapRepositoryActivity({ ...WIRE, lock: null }).lock).toBeNull();
  });
});
