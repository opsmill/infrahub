// PROTOTYPE design-jam commits-tab-pending-badge
import { ArrowDownToLineIcon, GitBranchIcon } from "lucide-react";

import { LinkTab } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import { getPendingSentence, getSplitSentences, type Scenario } from "../scenarios";
import { type CommitsTabProps, ProtoStage } from "../stage";

function CommitsTab({ to, scrollIntoViewOnActive }: CommitsTabProps) {
  return (
    <LinkTab to={to} scrollIntoViewOnActive={scrollIntoViewOnActive}>
      Commits
    </LinkTab>
  );
}

function getStripLines(scenario: Scenario) {
  if (scenario.split) {
    const sentences = getSplitSentences(scenario.split);
    return [
      { icon: GitBranchIcon, sentence: sentences.behind, action: "" },
      { icon: ArrowDownToLineIcon, sentence: sentences.pendingOnMain, action: sentences.action },
    ];
  }
  const sentence = getPendingSentence(scenario);
  if (!sentence) return [];

  return [
    {
      icon: scenario.meaning === "rebase" ? GitBranchIcon : ArrowDownToLineIcon,
      sentence,
      action: scenario.action,
    },
  ];
}

function StatusStrip({ scenario, compact }: { scenario: Scenario; compact?: boolean }) {
  const lines = getStripLines(scenario);
  if (lines.length === 0) return null;

  return (
    <div
      role="note"
      className={classNames(
        "flex flex-col gap-1 border-warning-border bg-warning-surface text-warning",
        compact ? "w-fit rounded-md border px-2.5 py-1 text-xs" : "border-b px-3 py-2.5 text-sm"
      )}
    >
      {lines.map(({ icon: Icon, sentence, action }) => (
        <div key={sentence} className="flex items-center gap-2.5">
          <Icon
            className={classNames("shrink-0", compact ? "size-3.5" : "size-4")}
            aria-hidden="true"
          />
          <p className="text-pretty">
            <span className="font-semibold tabular-nums">{sentence}.</span> {action}
          </p>
        </div>
      ))}
    </div>
  );
}

function getNoStripReason(scenario: Scenario) {
  if (scenario.warning) return "the warning notice";
  if (scenario.emptyState) return "the empty state";
  if (scenario.error) return "the error";
  if (scenario.condition === "LOADING") return "the loading indicator";
  return "the commit list";
}

function OverviewPreview({ scenario }: { scenario: Scenario }) {
  if (getStripLines(scenario).length > 0) return <StatusStrip scenario={scenario} compact />;

  return (
    <p className="text-subtle-muted text-xs">
      Inside the tab: no status strip, only {getNoStripReason(scenario)}
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
      showSplit
    />
  );
}
