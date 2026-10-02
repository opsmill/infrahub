import {
  WORKFLOW_LABELS,
  WORKFLOW_PREFIX_LABELS,
} from "@/entities/tasks/domain/model/workflow-labels";

const humanize = (workflow: string) => {
  const words = workflow.replace(/[-_]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

export function getWorkflowLabel(workflow: string | null): string {
  if (!workflow) return "—";

  return (
    WORKFLOW_LABELS[workflow] ??
    WORKFLOW_PREFIX_LABELS.find(([prefix]) => workflow.startsWith(prefix))?.[1] ??
    humanize(workflow)
  );
}
