import type {
  RepositoryActivityBranchOutcome,
  RepositoryActivityOperation,
  RepositoryActivityPhase,
} from "@/shared/api/graphql/generated/types";

export interface RepositoryActiveRun {
  runId: string;
  operation: RepositoryActivityOperation;
  /** Null until the run reports its first step, and for an operation without separate steps. */
  phase: RepositoryActivityPhase | null;
  /** Null while fetching, because a fetch covers every branch. */
  branchName: string | null;
  workerId: string;
  startedAt: string;
}

export interface RepositoryRunBranchOutcome {
  branchName: string;
  outcome: RepositoryActivityBranchOutcome;
}

export interface RepositoryLastRun {
  operation: RepositoryActivityOperation;
  finishedAt: string;
  branches: RepositoryRunBranchOutcome[];
}

export interface RepositoryLock {
  workerId: string;
  /** When the worker asked for the lock, which can be earlier than when it got it. */
  requestedAt: string | null;
}

export interface RepositoryActivity {
  activeRuns: RepositoryActiveRun[];
  /** Newest first, one per operation. */
  lastRuns: RepositoryLastRun[];
  lock: RepositoryLock | null;
}
