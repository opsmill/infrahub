// PROTOTYPE design-jam commits-tab-pending-badge
import { Spinner, Tooltip } from "@infrahub/ui";
import { ArrowDownToLineIcon, GitBranchIcon } from "lucide-react";
import { type ReactNode, useRef, useState } from "react";

import { LinkTab } from "@/shared/components/ui/link";
import { formatNumberDisplay } from "@/shared/utils/number";

import { getPendingSentence } from "../scenarios";
import { type CommitsTabProps, ProtoStage } from "../stage";

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
    if (hint) timer.current = setTimeout(() => setOpen(true), delay);
  };
  const hide = () => {
    clearTimeout(timer.current);
    setOpen(false);
  };

  // Opened by hand because a non-interactive trigger inside a link never receives keyboard focus.
  return (
    <LinkTab
      to={to}
      scrollIntoViewOnActive={scrollIntoViewOnActive}
      aria-label={accessibleName}
      onMouseEnter={() => show(200)}
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

function CommitsTab({ scenario, to, scrollIntoViewOnActive }: CommitsTabProps) {
  const sentence = getPendingSentence(scenario);
  const Icon = scenario.meaning === "rebase" ? GitBranchIcon : ArrowDownToLineIcon;

  return (
    <HintedTab
      to={to}
      scrollIntoViewOnActive={scrollIntoViewOnActive}
      hint={sentence && `${sentence}. ${scenario.action}`}
      accessibleName={sentence ? `Commits, ${sentence}` : undefined}
    >
      Commits
      {scenario.condition === "LOADING" && <Spinner />}
      {sentence && scenario.count ? (
        <span
          aria-hidden="true"
          className="inline-flex h-5 items-center gap-1 rounded-full border border-warning-border bg-warning-surface px-1.5 font-medium text-warning text-xs tabular-nums"
        >
          <Icon className="size-3 shrink-0" strokeWidth={2.25} />
          {formatNumberDisplay(scenario.count)}
        </span>
      ) : null}
    </HintedTab>
  );
}

export function PillRev01({ scenario }: { scenario: string }) {
  return (
    <ProtoStage scenarioOption={scenario} renderCommitsTab={(props) => <CommitsTab {...props} />} />
  );
}
