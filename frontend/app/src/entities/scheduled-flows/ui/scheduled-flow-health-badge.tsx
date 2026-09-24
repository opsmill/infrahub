import { Icon } from "@/shared/components/display/icon";
import { Badge, type BadgeProps } from "@/shared/components/ui/badge";

import {
  SCHEDULED_FLOW_HEALTH_CANCELLED,
  SCHEDULED_FLOW_HEALTH_DESCRIPTIONS,
  SCHEDULED_FLOW_HEALTH_FAILED,
  SCHEDULED_FLOW_HEALTH_HEALTHY,
  SCHEDULED_FLOW_HEALTH_LABELS,
  SCHEDULED_FLOW_HEALTH_NEVER_RUN,
  SCHEDULED_FLOW_HEALTH_NO_RECENT_RUNS,
  SCHEDULED_FLOW_HEALTH_OVERDUE,
  SCHEDULED_FLOW_HEALTH_PAUSED,
  type ScheduledFlowHealth,
} from "@/entities/scheduled-flows/domain/model/scheduled-flow";

// Every verdict carries an icon and a word. Colour alone would be unreadable to anyone who cannot
// distinguish the hues, and the ticket's whole point is that a stalled flow must be obvious.
const HEALTH_PRESENTATION: Record<
  ScheduledFlowHealth,
  { variant: BadgeProps["variant"]; icon: string }
> = {
  [SCHEDULED_FLOW_HEALTH_OVERDUE]: { variant: "red", icon: "mdi:clock-alert-outline" },
  [SCHEDULED_FLOW_HEALTH_FAILED]: { variant: "red", icon: "mdi:close-circle-outline" },
  [SCHEDULED_FLOW_HEALTH_CANCELLED]: { variant: "red-outline", icon: "mdi:cancel" },
  [SCHEDULED_FLOW_HEALTH_NO_RECENT_RUNS]: { variant: "yellow", icon: "mdi:help-circle-outline" },
  [SCHEDULED_FLOW_HEALTH_NEVER_RUN]: { variant: "gray-outline", icon: "mdi:timer-sand-empty" },
  [SCHEDULED_FLOW_HEALTH_PAUSED]: { variant: "gray", icon: "mdi:pause-circle-outline" },
  [SCHEDULED_FLOW_HEALTH_HEALTHY]: { variant: "green", icon: "mdi:check-circle-outline" },
};

interface ScheduledFlowHealthBadgeProps {
  health: ScheduledFlowHealth;
}

export function ScheduledFlowHealthBadge({ health }: ScheduledFlowHealthBadgeProps) {
  const presentation = HEALTH_PRESENTATION[health];
  const label = SCHEDULED_FLOW_HEALTH_LABELS[health];

  if (!presentation) return <Badge variant="gray">{health}</Badge>;

  return (
    <Badge
      variant={presentation.variant}
      className="gap-1"
      title={SCHEDULED_FLOW_HEALTH_DESCRIPTIONS[health]}
      data-testid={`scheduled-flow-health-${health}`}
    >
      <Icon icon={presentation.icon} aria-hidden />
      {label}
    </Badge>
  );
}
