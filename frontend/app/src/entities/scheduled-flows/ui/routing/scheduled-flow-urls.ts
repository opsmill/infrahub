import { constructPath } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

interface ScheduledFlowRunsUrlParams {
  workflowName: string;
  workflowType?: string | null;
}

/**
 * The Tasks list scoped to one workflow. No state filter is applied: the failed and cancelled runs
 * are exactly what the drill-down exists to show.
 */
export function getScheduledFlowRunsUrl({
  workflowName,
  workflowType,
}: ScheduledFlowRunsUrlParams): string {
  const filters: Array<{ name: string; value: unknown }> = [
    { name: "workflow__value", value: workflowName },
  ];

  if (workflowType) {
    filters.push({ name: "workflow_type__value", value: workflowType });
  }

  return constructPath("/tasks", [{ name: QSP.FILTER, value: JSON.stringify(filters) }]);
}
