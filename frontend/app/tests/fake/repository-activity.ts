import type {
  RepositoryActiveRun,
  RepositoryActivity,
  RepositoryLastRun,
  RepositoryLock,
} from "@/entities/repository/domain/model/repository-activity";

export const WORKER_ID = "3f9c1a2e-7b4d-4e61-9a0f-c2d8e5b71f04";

export const generateActiveRun = (
  overrides: Partial<RepositoryActiveRun> = {}
): RepositoryActiveRun => ({
  runId: "run-1",
  operation: "SYNC",
  phase: "APPLYING",
  branchName: "release-1.12",
  workerId: WORKER_ID,
  startedAt: "2026-10-14T14:00:00Z",
  ...overrides,
});

export const generateLastRun = (overrides: Partial<RepositoryLastRun> = {}): RepositoryLastRun => ({
  operation: "SYNC",
  finishedAt: "2026-10-14T13:58:00Z",
  branches: [{ branchName: "main", outcome: "IMPORTED" }],
  ...overrides,
});

export const generateLock = (overrides: Partial<RepositoryLock> = {}): RepositoryLock => ({
  workerId: WORKER_ID,
  requestedAt: "2026-10-14T14:00:05Z",
  ...overrides,
});

export const generateActivity = (
  overrides: Partial<RepositoryActivity> = {}
): RepositoryActivity => ({
  activeRuns: [],
  lastRuns: [],
  lock: null,
  ...overrides,
});
