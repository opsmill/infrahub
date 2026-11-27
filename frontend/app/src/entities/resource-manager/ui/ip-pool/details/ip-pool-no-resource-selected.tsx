import { Card } from "@infrahub/ui";
import { ArrowRightIcon } from "lucide-react";

import { Col, Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

import { IP_ADDRESS_POOL, type IpPoolKind } from "@/entities/resource-manager/domain/model/pool";

const FADE_OUT = "[mask-image:linear-gradient(to_bottom,black_55%,transparent)]";
const TABLE_ROW =
  "grid h-7 grid-cols-[1fr_1.3fr_0.9fr] items-center gap-3 border-border/50 border-b px-3";

const RESOURCE_ITEMS = [
  { labelWidth: "w-20", usagePercent: 30, isSelected: false },
  { labelWidth: "w-24", usagePercent: 60, isSelected: true },
  { labelWidth: "w-[88px]", usagePercent: 15, isSelected: false },
  { labelWidth: "w-20", usagePercent: 40, isSelected: false },
];

const TABLE_ROW_WIDTHS = [
  ["w-20", "w-24"],
  ["w-16", "w-12"],
  ["w-20", "w-28"],
  ["w-[72px]", "w-16"],
  ["w-20", "w-20"],
];

interface BarProps {
  className: string;
}

function Bar({ className }: BarProps) {
  return <span className={classNames("block h-1.5 rounded-full", className)} />;
}

function ResourceListSketch() {
  return (
    <Card className={classNames("w-44 gap-1 overflow-hidden rounded-xl p-1", FADE_OUT)}>
      {RESOURCE_ITEMS.map(({ labelWidth, usagePercent, isSelected }) => (
        <Col
          key={`${labelWidth}-${usagePercent}`}
          className={classNames("gap-2 rounded-lg p-2", isSelected && "bg-highlight")}
        >
          <Bar
            className={classNames(labelWidth, isSelected ? "bg-foreground/80" : "bg-foreground/50")}
          />
          <Row className="gap-1.5">
            <span className="block h-1 flex-1 overflow-hidden rounded-full bg-content-strong">
              <span
                className="block h-full rounded-full bg-accent-strong"
                style={{ width: `${usagePercent}%` }}
              />
            </span>
            <Bar className="w-4 bg-foreground-muted/35" />
          </Row>
        </Col>
      ))}
    </Card>
  );
}

function AllocationsTableSketch() {
  return (
    <Card className={classNames("w-72 overflow-hidden rounded-xl", FADE_OUT)}>
      <Row className="h-8 gap-1.5 border-b px-3">
        <Bar className="w-28 bg-foreground/70" />
        <Bar className="w-5 bg-foreground-muted/40" />
      </Row>
      <div className={TABLE_ROW}>
        <Bar className="w-10 bg-foreground-muted/35" />
        <Bar className="w-10 bg-foreground-muted/35" />
        <Bar className="w-10 bg-foreground-muted/35" />
      </div>
      {TABLE_ROW_WIDTHS.map(([addressWidth, identifierWidth]) => (
        <div key={`${addressWidth}-${identifierWidth}`} className={TABLE_ROW}>
          <Bar className={classNames(addressWidth, "bg-foreground/60")} />
          <Bar className={classNames(identifierWidth, "bg-content-strong")} />
          <Bar className="w-14 bg-content-strong" />
        </div>
      ))}
    </Card>
  );
}

export interface IpPoolNoResourceSelectedProps {
  poolKind: IpPoolKind;
}

export function IpPoolNoResourceSelected({ poolKind }: IpPoolNoResourceSelectedProps) {
  const allocatedItems = poolKind === IP_ADDRESS_POOL ? "IP addresses" : "IP prefixes";

  return (
    <Col className="@container min-h-64 grow items-center justify-center gap-6 self-stretch rounded-2xl border border-border-strong border-dashed p-6">
      <Row aria-hidden className="pointer-events-none select-none gap-3">
        <Row className="@xl:flex hidden gap-3">
          <ResourceListSketch />
          <ArrowRightIcon className="size-4 shrink-0 text-foreground-muted" />
        </Row>
        <AllocationsTableSketch />
      </Row>
      <Col className="items-center gap-1 text-center">
        <h2 className="font-medium text-sm">Select a resource prefix</h2>
        <p className="max-w-72 text-balance text-foreground-muted text-sm">
          See all {allocatedItems} allocated from it.
        </p>
      </Col>
    </Col>
  );
}
