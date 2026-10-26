import { Tooltip } from "@infrahub/ui";
import type React from "react";

import { Col, Row } from "@/shared/components/container";
import MultipleProgressBar from "@/shared/components/stats/multiple-progress-bar";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import type { NumberPoolUsage } from "@/entities/resource-manager/domain/model/number-pool";

const percentOf = (part: number, total: number) => (total === 0 ? 0 : (part / total) * 100);

export const formatUsagePercent = (value: number) => {
  if (value === 0) return "0%";
  if (value < 0.1) return "<0.1%";
  if (value < 10) return `${value.toFixed(1).replace(/\.0$/, "")}%`;
  return `${Math.floor(value)}%`;
};

const formatUsedOfSize = (used: number, size: number | null) =>
  size === null
    ? formatNumberDisplay(used)
    : `${formatNumberDisplay(used)} of ${formatNumberDisplay(size)}`;

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

interface UtilizationFiguresRowProps {
  label: string;
  value: number;
  dotClassName?: string;
}

function UtilizationFiguresRow({ label, value, dotClassName }: UtilizationFiguresRowProps) {
  return (
    <Row className="justify-between gap-5">
      <Row className="text-white/70">
        {dotClassName && (
          <span className={classNames("size-2 shrink-0 rounded-full", dotClassName)} />
        )}
        {label}
      </Row>
      <span>{formatNumberDisplay(value)}</span>
    </Row>
  );
}

interface UtilizationFiguresTooltipProps {
  usage: NumberPoolUsage;
  children: React.ReactNode;
}

function UtilizationFiguresTooltip({ usage, children }: UtilizationFiguresTooltipProps) {
  const { size, used, usedDefaultBranch, usedBranches } = usage;
  // the dots match the bar segments, which a usage without a size does not draw
  const hasBarSegments = size !== null;

  return (
    <Tooltip
      nonInteractiveTrigger
      message={
        <Col className="gap-1 text-xs tabular-nums">
          <UtilizationFiguresRow
            label="Default branch"
            value={usedDefaultBranch}
            dotClassName={hasBarSegments ? "bg-accent-strong" : undefined}
          />
          <UtilizationFiguresRow
            label="Other branches"
            value={usedBranches}
            dotClassName={hasBarSegments ? "bg-accent-strong/45" : undefined}
          />
          <span className="my-0.5 h-px bg-white/15" />
          <Row className="justify-between gap-5 font-medium">
            <span>Used</span>
            <span>{formatUsedOfSize(used, size)}</span>
          </Row>
        </Col>
      }
    >
      <span className="min-w-11 shrink-0 whitespace-nowrap text-right font-medium text-foreground text-xs tabular-nums">
        {children}
      </span>
    </Tooltip>
  );
}

interface UsageBarWithoutSizeProps {
  usage: NumberPoolUsage;
}

function UsageBarWithoutSize({ usage }: UsageBarWithoutSizeProps) {
  return (
    <Row>
      <div
        role="img"
        aria-label="No upper limit"
        className="h-1.5 w-full min-w-6 rounded-full bg-accent-strong/10 bg-stripes-accent-strong/15"
      />
      <UtilizationFiguresTooltip usage={usage}>
        {formatNumberDisplay(usage.used)}
      </UtilizationFiguresTooltip>
    </Row>
  );
}

export interface NumberPoolUsageBarProps {
  usage: NumberPoolUsage;
}

export function NumberPoolUsageBar({ usage }: NumberPoolUsageBarProps) {
  const { size, utilization, usedDefaultBranch, usedBranches } = usage;
  if (size === null || utilization === null) return <UsageBarWithoutSize usage={usage} />;

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
      <UtilizationFiguresTooltip usage={usage}>
        {formatUsagePercent(utilization)}
      </UtilizationFiguresTooltip>
    </Row>
  );
}
