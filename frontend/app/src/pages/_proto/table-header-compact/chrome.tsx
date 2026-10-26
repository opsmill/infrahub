// PROTOTYPE design-jam table-header-compact — static replicas of today's detail page chrome, with slots.
import { Button } from "@infrahub/ui";
import { ChevronDownIcon, PencilIcon, RefreshCwIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { classNames } from "@/shared/utils/common";

export function PageCard({ children }: { children: ReactNode }) {
  return <Content.Card className="h-full grow overflow-hidden">{children}</Content.Card>;
}

export function ObjectHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <Row className="items-center gap-2 px-4 py-3">
      <h1 className="truncate font-bold text-xl">{title}</h1>
      <Button variant="outline" size="sm" shape="square" className="ml-auto" aria-label="Refresh">
        <RefreshCwIcon />
      </Button>
      {actions}
      <Button variant="outline" size="sm">
        <PencilIcon /> Edit
      </Button>
      <Button variant="outline" size="sm">
        Actions <ChevronDownIcon />
      </Button>
    </Row>
  );
}

export function Tabs({
  tabs,
  active,
  counts,
  trailing,
}: {
  tabs: readonly string[];
  active: string;
  counts?: Record<string, number | undefined>;
  trailing?: ReactNode;
}) {
  return (
    <Row className="items-end gap-4 border-b px-4">
      {tabs.map((tab) => (
        <span
          key={tab}
          className={classNames(
            "inline-flex h-11 items-center gap-2 border-b-2 px-3 py-2 font-medium text-sm",
            tab === active
              ? "border-custom-blue-600 text-custom-blue-600"
              : "border-transparent text-foreground-muted"
          )}
        >
          {tab}
          {counts?.[tab] !== undefined && (
            <span className="rounded-full bg-neutral-100 px-1.5 text-foreground-muted text-xs dark:bg-neutral-800">
              {counts[tab]}
            </span>
          )}
        </span>
      ))}
      {trailing && <Row className="ml-auto items-center gap-2 self-center">{trailing}</Row>}
    </Row>
  );
}
