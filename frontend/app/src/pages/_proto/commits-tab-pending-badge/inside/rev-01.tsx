// PROTOTYPE design-jam commits-tab-pending-badge
import { ArrowDownToLineIcon, GitBranchIcon } from "lucide-react";

import { LinkTab } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import { getPendingSentence, type Scenario } from "../scenarios";
import { type CommitsTabProps, ProtoStage } from "../stage";

function CommitsTab({ to, scrollIntoViewOnActive }: CommitsTabProps) {
  return (
    <LinkTab to={to} scrollIntoViewOnActive={scrollIntoViewOnActive}>
      Commits
    </LinkTab>
  );
}

function StatusStrip({ scenario, compact }: { scenario: Scenario; compact?: boolean }) {
  const sentence = getPendingSentence(scenario);
  if (!sentence) return null;

  const Icon = scenario.meaning === "rebase" ? GitBranchIcon : ArrowDownToLineIcon;

  return (
    <div
      role="note"
      className={classNames(
        "flex items-center gap-2.5 border-warning-border bg-warning-surface text-warning",
        compact ? "w-fit rounded-md border px-2.5 py-1 text-xs" : "border-b px-3 py-2.5 text-sm"
      )}
    >
      <Icon
        className={classNames("shrink-0", compact ? "size-3.5" : "size-4")}
        aria-hidden="true"
      />
      <p className="text-pretty">
        <span className="font-semibold tabular-nums">{sentence}.</span> {scenario.action}
      </p>
    </div>
  );
}

function OverviewPreview({ scenario }: { scenario: Scenario }) {
  if (getPendingSentence(scenario)) return <StatusStrip scenario={scenario} compact />;

  return (
    <p className="text-subtle-muted text-xs">
      {scenario.warning
        ? "Inside the tab: no status strip, the rewritten-history warning instead"
        : "Inside the tab: no status strip"}
    </p>
  );
}

export function InsideRev01({ scenario }: { scenario: string }) {
  return (
    <ProtoStage
      scenarioOption={scenario}
      renderCommitsTab={(props) => <CommitsTab {...props} />}
      insideTop={(s) => <StatusStrip scenario={s} />}
      overviewPreview={(s) => <OverviewPreview scenario={s} />}
      hideCountNotice
    />
  );
}
