import { Col, Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Table, type tColumn } from "@/shared/components/table/table";
import { Badge } from "@/shared/components/ui/badge";

import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";
import {
  getScheduleSentence,
  type ScheduledFlowHealth,
} from "@/entities/scheduled-flows/domain/model/scheduled-flow";
import type { ScheduledFlowItem } from "@/entities/scheduled-flows/domain/use-cases/get-scheduled-flows";
import { useGetScheduledFlows } from "@/entities/scheduled-flows/ui/queries/get-scheduled-flows.query";
import { getScheduledFlowRunsUrl } from "@/entities/scheduled-flows/ui/routing/scheduled-flow-urls";
import { ScheduledFlowHealthBadge } from "@/entities/scheduled-flows/ui/scheduled-flow-health-badge";
import { WORKFLOW_TYPE_LABELS } from "@/entities/tasks/domain/model/task";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";
import { getStateBadge } from "@/entities/tasks/ui/task-item-details";

const COLUMNS: tColumn[] = [
  { name: "name", label: "Name" },
  { name: "workflow_type", label: "Type" },
  { name: "schedule", label: "Schedule" },
  { name: "health", label: "Health" },
  { name: "last_outcome", label: "Last outcome" },
  { name: "last_run_at", label: "Last run" },
  { name: "recent_outcomes", label: "Last 24 hours" },
];

function RecentOutcomes({ outcomes }: { outcomes: ScheduledFlowItem["recent_outcomes"] }) {
  if (!outcomes?.counts?.length) {
    return <span className="text-subtle-muted text-xs">No runs</span>;
  }

  // Whatever states come back are rendered, SCHEDULED included: during a stall "1440 scheduled,
  // 0 completed" is the signal, not noise.
  return (
    <Row className="flex-wrap gap-1">
      {outcomes.counts.map(({ state, count }) => (
        <Badge key={state} variant="gray-outline">
          {count} {state.toLowerCase()}
        </Badge>
      ))}
    </Row>
  );
}

export function ScheduledFlowItems() {
  const { data, error, isPending } = useGetScheduledFlows();

  const header = (
    <Row className="p-2">
      <RefreshButton className="rounded-md border-border-strong" queryKey={tasksQueryKeys.all} />
    </Row>
  );

  if (isPending) {
    return (
      <Col className="gap-0">
        {header}
        <LoadingIndicator className="p-4" />
      </Col>
    );
  }

  if (error) {
    return (
      <Col className="gap-0">
        {header}
        <ErrorScreen
          message={`Something went wrong when fetching scheduled flows. ${error.message}`}
        />
      </Col>
    );
  }

  // The backend orders unhealthy-first; re-sorting here would let the list disagree with the badges.
  const rows = data.flows.map((flow) => {
    const workflowTypeLabel = flow.workflow_type
      ? WORKFLOW_TYPE_LABELS[flow.workflow_type]
      : "Unknown";
    const scheduleSentence = getScheduleSentence({
      cron: flow.cron,
      intervalSeconds: flow.interval_seconds,
      nextRunAt: flow.next_run_at,
      timezone: flow.timezone,
    });

    return {
      link: getScheduledFlowRunsUrl({ workflowName: flow.name, workflowType: flow.workflow_type }),
      values: {
        name: { value: flow.name, display: flow.name },
        workflow_type: { value: flow.workflow_type, display: workflowTypeLabel },
        schedule: { value: flow.cron, display: scheduleSentence },
        health: {
          value: flow.health,
          display: <ScheduledFlowHealthBadge health={flow.health as ScheduledFlowHealth} />,
        },
        last_outcome: {
          value: flow.latest_run?.state,
          display: flow.latest_run?.state ? getStateBadge[flow.latest_run.state] : "—",
        },
        last_run_at: {
          value: flow.latest_run?.expected_start_time,
          display: flow.latest_run?.expected_start_time ? (
            <DateDisplay date={flow.latest_run.expected_start_time} />
          ) : (
            "—"
          ),
        },
        recent_outcomes: {
          value: flow.recent_outcomes?.total,
          display: <RecentOutcomes outcomes={flow.recent_outcomes} />,
        },
      },
    };
  });

  return (
    <Col className="gap-0">
      {header}

      <Table columns={COLUMNS} rows={rows} className="border-none" />

      {data.catalogueOnly.length > 0 && (
        <p className="p-2 text-subtle-muted text-xs">
          Declared with a schedule but not registered in the task manager:{" "}
          {data.catalogueOnly.join(", ")}
        </p>
      )}
    </Col>
  );
}
