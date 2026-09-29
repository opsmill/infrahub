import {
  BRANCH_MERGE_WORKFLOW,
  BRANCH_REBASE_WORKFLOW,
  BRANCH_VALIDATE_WORKFLOW,
} from "@/entities/tasks/domain/model/task";

const WORKFLOW_LABELS: Record<string, string> = {
  "git-repository-add-read-write": "Import",
  "git-repository-add-read-only": "Import",
  "git-repository-import-object": "Import",
  "git-read-only-repository-import-last-commit": "Import",
  "git-repository-pull-read-only": "Import",
  "sync-git-repo-with-origin": "Sync",
  git_repositories_sync: "Sync",
  "generator-run": "Generator",
  "generator-definition-run": "Generator",
  "request-generator-definition-run": "Generator",
  "artifact-generate": "Artifacts",
  "artifact-definition-generate": "Artifacts",
  request_artifact_definitions_generate: "Artifacts",
  "git-repository-check-artifact-create": "Artifacts",
  [BRANCH_VALIDATE_WORKFLOW]: "Validate",
  [BRANCH_REBASE_WORKFLOW]: "Rebase",
  [BRANCH_MERGE_WORKFLOW]: "Merge",
  "branch-merge": "Merge",
  "git-repository-merge": "Merge",
};

export function getWorkflowLabel(workflow: string | null): string {
  if (!workflow) return "—";

  return WORKFLOW_LABELS[workflow] ?? workflow;
}
