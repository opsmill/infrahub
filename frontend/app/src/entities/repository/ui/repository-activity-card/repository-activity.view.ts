import type {
  RepositoryActivityOperation,
  RepositoryActivityPhase,
} from "@/shared/api/graphql/generated/types";

import type {
  RepositoryActiveRun,
  RepositoryLastRun,
} from "@/entities/repository/domain/model/repository-activity";
import { countBranchOutcomes } from "@/entities/repository/domain/rules/count-branch-outcomes";

const OPERATION_LABELS: Record<RepositoryActivityOperation, string> = {
  SYNC: "Sync",
  REIMPORT: "Reimport",
  PULL: "Pull",
  ADD: "Add",
  BRANCH_CREATE: "Branch creation",
  MERGE: "Merge",
};

const PHASE_LABELS: Record<RepositoryActivityPhase, string> = {
  FETCHING: "Fetching",
  BUILDING: "Building",
  APPLYING: "Applying",
};

/** "DRIFT_CHECK" reads "Drift check", so a value added to the API after this build still reads well. */
export function humanizeEnumValue(value: string): string {
  const words = value.toLowerCase().replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function lookUpLabel(labels: Record<string, string>, value: string): string {
  return labels[value] ?? humanizeEnumValue(value);
}

export function getOperationLabel(operation: RepositoryActivityOperation): string {
  return lookUpLabel(OPERATION_LABELS, operation);
}

/** "Applying release-1.12", "Fetching all branches", or the branch alone for an operation without steps. */
export function getRunProgressText({ phase, branchName }: RepositoryActiveRun): string {
  if (!phase) return branchName ?? "";

  const branch = branchName ?? (phase === "FETCHING" ? "all branches" : null);
  return [lookUpLabel(PHASE_LABELS, phase), branch].filter(Boolean).join(" ");
}

export interface RunOutcomeParts {
  failed: string | null;
  changed: string | null;
}

/** A single branch is named ("main failed"); several are counted ("2 failed", "9 changed"). */
export function getRunOutcomeParts({ branches }: RepositoryLastRun): RunOutcomeParts {
  const { changed, failed } = countBranchOutcomes(branches);
  const [onlyBranch] = branches;

  if (branches.length === 1 && onlyBranch && changed + failed === 1) {
    return {
      failed: failed ? `${onlyBranch.branchName} failed` : null,
      changed: changed ? `${onlyBranch.branchName} changed` : null,
    };
  }

  return {
    failed: failed ? `${failed} failed` : null,
    changed: changed ? `${changed} changed` : null,
  };
}

/** "45s", "1m 04s", "2h 05m": the unit that matters for a run of that length. */
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");

  if (hours > 0) return `${hours}h ${pad(minutes)}m`;
  if (minutes > 0) return `${minutes}m ${pad(seconds)}s`;
  return `${seconds}s`;
}
