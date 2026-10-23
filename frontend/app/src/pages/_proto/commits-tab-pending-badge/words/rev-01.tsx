// PROTOTYPE design-jam commits-tab-pending-badge
import { Spinner, Tooltip } from "@infrahub/ui";
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
        <span ref={triggerRef} className="inline-flex items-center gap-1.5">
          {children}
        </span>
      </Tooltip>
    </LinkTab>
  );
}

function CommitsTab({ scenario, to, scrollIntoViewOnActive }: CommitsTabProps) {
  const sentence = getPendingSentence(scenario);
  const words = scenario.count
    ? `${formatNumberDisplay(scenario.count)} ${scenario.meaning === "rebase" ? "behind" : "to import"}`
    : null;

  return (
    <HintedTab
      to={to}
      scrollIntoViewOnActive={scrollIntoViewOnActive}
      hint={sentence && `${sentence}. ${scenario.action}`}
      accessibleName={sentence ? `Commits, ${sentence}` : undefined}
    >
      Commits
      {scenario.condition === "LOADING" && <Spinner />}
      {words && (
        <span aria-hidden="true" className="inline-flex items-center gap-1.5 font-normal">
          <span className="text-subtle-muted">·</span>
          <span className="text-warning tabular-nums">{words}</span>
        </span>
      )}
    </HintedTab>
  );
}

export function WordsRev01({ scenario }: { scenario: string }) {
  return (
    <ProtoStage scenarioOption={scenario} renderCommitsTab={(props) => <CommitsTab {...props} />} />
  );
}
