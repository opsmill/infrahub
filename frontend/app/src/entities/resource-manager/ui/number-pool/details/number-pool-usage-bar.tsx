import { Tooltip } from "@infrahub/ui";

import { Col, Row } from "@/shared/components/container";
import MultipleProgressBar from "@/shared/components/stats/multiple-progress-bar";
import { formatNumberDisplay } from "@/shared/utils/number";

import type { NumberPoolUsage } from "@/entities/resource-manager/domain/model/number-pool";

const percentOf = (part: number, total: number) => (total === 0 ? 0 : (part / total) * 100);

export const formatUsagePercent = (value: number) => {
  if (value === 0) return "0%";
  if (value < 0.1) return "<0.1%";
  if (value < 10) return `${value.toFixed(1).replace(/\.0$/, "")}%`;
  return `${Math.floor(value)}%`;
};

const formatUsedOfSize = (used: number, size: number) =>
  `${formatNumberDisplay(used)} of ${formatNumberDisplay(size)}`;

interface UtilizationTooltipMessageProps {
  title: string;
  value: string;
}

function UtilizationTooltipMessage({ title, value }: UtilizationTooltipMessageProps) {
  return (
    <Col className="gap-0.5">
      <span className="text-white/70 text-xxs">{title}</span>
      <span className="tabular-nums">{value}</span>
    </Col>
  );
}

export interface NumberPoolUsageBarProps {
  usage: NumberPoolUsage;
}

export function NumberPoolUsageBar({ usage }: NumberPoolUsageBarProps) {
  const { size, used, usedDefaultBranch, usedBranches, utilization } = usage;

  return (
    <Row>
      <MultipleProgressBar
        className="h-1.5"
        aria-label="Usage"
        elements={[
          {
            value: percentOf(usedDefaultBranch, size),
            color: "var(--accent-strong)",
            tooltip: (
              <UtilizationTooltipMessage
                title="Default branch"
                value={formatUsedOfSize(usedDefaultBranch, size)}
              />
            ),
          },
          {
            value: percentOf(usedBranches, size),
            color: "color-mix(in oklch, var(--accent-strong) 45%, transparent)",
            tooltip: (
              <UtilizationTooltipMessage
                title="Other branches only"
                value={formatUsedOfSize(usedBranches, size)}
              />
            ),
          },
        ]}
      />
      <Tooltip
        nonInteractiveTrigger
        message={<UtilizationTooltipMessage title="Used" value={formatUsedOfSize(used, size)} />}
      >
        <span className="w-11 shrink-0 text-right font-medium text-foreground text-xs tabular-nums">
          {formatUsagePercent(utilization)}
        </span>
      </Tooltip>
    </Row>
  );
}
