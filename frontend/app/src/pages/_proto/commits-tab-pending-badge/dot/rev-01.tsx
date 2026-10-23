// PROTOTYPE design-jam commits-tab-pending-badge
import { Spinner, Tooltip } from "@infrahub/ui";
import { type ReactNode, useRef, useState } from "react";

import { LinkTab } from "@/shared/components/ui/link";

import { getPendingSentence, getSplitSentences, type Scenario } from "../scenarios";
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

function getSignal(scenario: Scenario) {
  if (scenario.split) {
    const sentences = getSplitSentences(scenario.split);
    return {
      hint: `${sentences.behind}. ${sentences.pendingOnMain}. ${sentences.action}`,
      name: `Commits, ${sentences.behind}, ${sentences.pendingOnMain}`,
    };
  }
  const sentence = getPendingSentence(scenario);
  return sentence
    ? { hint: `${sentence}. ${scenario.action}`, name: `Commits, ${sentence}` }
    : null;
}

function CommitsTab({
  scenario,
  to,
  scrollIntoViewOnActive,
  dotSize,
}: CommitsTabProps & { dotSize: number }) {
  const signal = getSignal(scenario);

  return (
    <HintedTab
      to={to}
      scrollIntoViewOnActive={scrollIntoViewOnActive}
      hint={signal?.hint ?? null}
      accessibleName={signal?.name}
    >
      Commits
      {scenario.condition === "LOADING" && <Spinner />}
      {signal && (
        <span
          aria-hidden="true"
          className="shrink-0 rounded-full bg-warning"
          style={{ width: dotSize, height: dotSize }}
        />
      )}
    </HintedTab>
  );
}

export function DotRev01({ scenario, dotSize }: { scenario: string; dotSize: number }) {
  return (
    <ProtoStage
      scenarioOption={scenario}
      renderCommitsTab={(props) => <CommitsTab {...props} dotSize={dotSize} />}
      showSplit
    />
  );
}
