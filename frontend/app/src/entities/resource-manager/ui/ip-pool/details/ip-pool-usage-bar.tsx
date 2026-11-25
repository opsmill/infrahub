import { Tooltip } from "@infrahub/ui";

import { Col, Row } from "@/shared/components/container";
import MultipleProgressBar from "@/shared/components/stats/multiple-progress-bar";

import type { IpPoolResourceUsage } from "@/entities/resource-manager/domain/model/ip-pool";
import { formatUsagePercent } from "@/entities/resource-manager/ui/pool/format-usage-percent";
import { UtilizationFiguresRow } from "@/entities/resource-manager/ui/pool/utilization-figures-row";
import { UtilizationTooltipMessage } from "@/entities/resource-manager/ui/pool/utilization-tooltip-message";

export interface IpPoolUsageBreakdownProps {
  usage: IpPoolResourceUsage;
}

export function IpPoolUsageBreakdown({ usage }: IpPoolUsageBreakdownProps) {
  return (
    <Col className="gap-1 text-xs tabular-nums">
      <UtilizationFiguresRow
        label="Default branch"
        value={formatUsagePercent(usage.utilizationDefaultBranch)}
        dotClassName="bg-accent-strong"
      />
      <UtilizationFiguresRow
        label="Other branches"
        value={formatUsagePercent(usage.utilizationBranches)}
        dotClassName="bg-accent-strong/45"
      />
      <span className="my-0.5 h-px bg-white/15" />
      <Row className="justify-between gap-5 font-medium">
        <span>Utilization</span>
        <span>{formatUsagePercent(usage.utilization)}</span>
      </Row>
    </Col>
  );
}

export interface IpPoolUsageBarProps {
  usage: IpPoolResourceUsage;
}

export function IpPoolUsageBar({ usage }: IpPoolUsageBarProps) {
  const { utilization, utilizationDefaultBranch, utilizationBranches } = usage;

  return (
    <Row>
      <MultipleProgressBar
        className="h-1.5"
        aria-label="Usage"
        elements={[
          {
            value: utilizationDefaultBranch,
            color: "var(--accent-strong)",
            tooltip: (
              <UtilizationTooltipMessage
                title="Default branch"
                value={formatUsagePercent(utilizationDefaultBranch)}
              />
            ),
          },
          {
            value: utilizationBranches,
            color: "color-mix(in oklch, var(--accent-strong) 45%, transparent)",
            tooltip: (
              <UtilizationTooltipMessage
                title="Other branches only"
                value={formatUsagePercent(utilizationBranches)}
              />
            ),
          },
        ]}
      />
      <Tooltip nonInteractiveTrigger message={<IpPoolUsageBreakdown usage={usage} />}>
        <span className="min-w-11 shrink-0 whitespace-nowrap text-right font-medium text-foreground text-xs tabular-nums">
          {formatUsagePercent(utilization)}
        </span>
      </Tooltip>
    </Row>
  );
}
