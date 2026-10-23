// PROTOTYPE design-jam commits-tab-pending-badge
import { Spinner, Tooltip } from "@infrahub/ui";
import { ArrowDownToLineIcon, GitBranchIcon, TriangleAlertIcon } from "lucide-react";
import { type ReactNode, useRef, useState } from "react";

import { LinkTab } from "@/shared/components/ui/link";
import { formatNumberDisplay } from "@/shared/utils/number";

import { getPendingSentence, type Scenario } from "../scenarios";
import { type CommitsTabProps, ProtoStage } from "../stage";

const TOOLTIP_DELAY_MS = 200;
const TOOLTIP_WARM_MS = 600;
const COUNT_CAP = 999;

let lastTooltipClosedAt = 0;

function HintedTab({
  to,
  scrollIntoViewOnActive,
  hint,
  children,
  accessibleName,
}: Omit<CommitsTabProps, "scenario"> & {
  hint: string | null;
  accessibleName?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const show = (delay: number) => {
    clearTimeout(timer.current);
    if (!hint) return;
    const isWarm = Date.now() - lastTooltipClosedAt < TOOLTIP_WARM_MS;
    timer.current = setTimeout(() => setOpen(true), isWarm ? 0 : delay);
  };
  const hide = () => {
    clearTimeout(timer.current);
    if (open) lastTooltipClosedAt = Date.now();
    setOpen(false);
  };

  // Opened by hand because a non-interactive trigger inside a link never receives keyboard focus.
  return (
    <LinkTab
      to={to}
      scrollIntoViewOnActive={scrollIntoViewOnActive}
      aria-label={accessibleName}
      onMouseEnter={() => show(TOOLTIP_DELAY_MS)}
      onMouseLeave={hide}
      onClick={hide}
      onFocus={(event) => {
        if (event.currentTarget.matches(":focus-visible")) show(0);
      }}
      onBlur={hide}
      onKeyDown={(event) => {
        if (event.key === "Escape") hide();
      }}
    >
      <Tooltip message={hint} isOpen={open} onOpenChange={setOpen} triggerRef={triggerRef}>
        <span ref={triggerRef} className="inline-flex items-center gap-2">
          {children}
        </span>
      </Tooltip>
    </LinkTab>
  );
}

const PILL =
  "inline-flex h-5 shrink-0 items-center gap-1 rounded-full border border-warning-border bg-warning-surface/60 px-1.5 font-medium text-warning text-xs tabular-nums";

const isReadOnly = (scenario: Scenario) => scenario.group === "D";

function getActionClause(scenario: Scenario) {
  const them = scenario.count === 1 ? "it" : "them";
  if (scenario.meaning === "rebase") return `rebase the branch to use ${them}`;
  if (isReadOnly(scenario)) return `run Import latest commit to use ${them}`;
  return `the next sync imports ${them}`;
}

const getWarningName = (scenario: Scenario) =>
  scenario.condition === "REWRITTEN" && scenario.meaning === "rebase"
    ? "diverged from main"
    : (scenario.warning?.label ?? "");

function getSignal(scenario: Scenario) {
  const sentence = getPendingSentence(scenario);
  if (sentence) {
    return { hint: `${sentence} — ${getActionClause(scenario)}`, name: `Commits, ${sentence}` };
  }
  if (scenario.warning) {
    return { hint: scenario.warning.hint, name: `Commits, ${getWarningName(scenario)}` };
  }
  return null;
}

const formatCappedCount = (count: number) =>
  count > COUNT_CAP ? `${formatNumberDisplay(COUNT_CAP)}+` : formatNumberDisplay(count);

function CommitsTab({ scenario, to, scrollIntoViewOnActive }: CommitsTabProps) {
  const signal = getSignal(scenario);
  const Icon = scenario.meaning === "rebase" ? GitBranchIcon : ArrowDownToLineIcon;

  return (
    <HintedTab
      to={to}
      scrollIntoViewOnActive={scrollIntoViewOnActive}
      hint={signal?.hint ?? null}
      accessibleName={signal?.name}
    >
      Commits
      {scenario.condition === "LOADING" && <Spinner />}
      {scenario.count ? (
        <span aria-hidden="true" className={PILL}>
          <Icon className="size-3 shrink-0" strokeWidth={2.25} />
          {formatCappedCount(scenario.count)}
        </span>
      ) : scenario.warning ? (
        <span aria-hidden="true" className={PILL}>
          <TriangleAlertIcon className="size-3 shrink-0" strokeWidth={2.25} />
        </span>
      ) : null}
    </HintedTab>
  );
}

export function PillRev02({ scenario }: { scenario: string }) {
  return (
    <ProtoStage
      scenarioOption={scenario}
      renderCommitsTab={(props) => <CommitsTab {...props} />}
      stickyCommitsTab
    />
  );
}
