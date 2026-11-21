import { Tooltip } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import MultipleProgressBar from "@/shared/components/stats/multiple-progress-bar";

import type { IpPoolResourceUsage } from "@/entities/resource-manager/domain/model/ip-pool";
import { formatUsagePercent } from "@/entities/resource-manager/ui/pool/format-usage-percent";
import { UtilizationTooltipMessage } from "@/entities/resource-manager/ui/pool/utilization-tooltip-message";

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
                title="This branch only"
                value={formatUsagePercent(utilizationBranches)}
              />
            ),
          },
        ]}
      />
      <Tooltip
        nonInteractiveTrigger
        message={<UtilizationTooltipMessage title="Used" value={formatUsagePercent(utilization)} />}
      >
        <span className="min-w-11 shrink-0 whitespace-nowrap text-right font-medium text-foreground text-xs tabular-nums">
          {formatUsagePercent(utilization)}
        </span>
      </Tooltip>
    </Row>
  );
}
