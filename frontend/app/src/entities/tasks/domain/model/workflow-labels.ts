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
  "create-branch": "Create branch",
  "branch-delete": "Delete branch",
  "git-repository-trigger-user-checks": "Checks",
  "git-repository-user-checks-definition-trigger": "Checks",
  "git-repository-trigger-internal-checks": "Checks",
  "git-repository-check-merge-conflict": "Checks",
  schema_validate_migrations: "Schema",
  "trigger-update-display-labels": "Display labels",
  "trigger-update-hfid": "HFID",
};

const PREFIX_LABELS: [prefix: string, label: string][] = [
  ["proposed-changed-", "Proposed change"],
  ["computed-attribute", "Computed attribute"],
  ["computed_attribute", "Computed attribute"],
  ["trigger_update_python_computed_attributes", "Computed attribute"],
  ["webhook", "Webhook"],
];

const humanize = (workflow: string) => {
  const words = workflow.replace(/[-_]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

export function getWorkflowLabel(workflow: string | null): string {
  if (!workflow) return "—";

  return (
    WORKFLOW_LABELS[workflow] ??
    PREFIX_LABELS.find(([prefix]) => workflow.startsWith(prefix))?.[1] ??
    humanize(workflow)
  );
}
