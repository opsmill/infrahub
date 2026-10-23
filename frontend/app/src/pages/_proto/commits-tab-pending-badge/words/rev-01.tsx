// PROTOTYPE design-jam commits-tab-pending-badge
import { Spinner, Tooltip } from "@infrahub/ui";
import { type ReactNode, useRef, useState } from "react";

import { LinkTab } from "@/shared/components/ui/link";
import { formatNumberDisplay } from "@/shared/utils/number";

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
        <span ref={triggerRef} className="inline-flex items-center gap-1.5">
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
      words: [
        `${formatNumberDisplay(scenario.split.behind)} behind`,
        `${formatNumberDisplay(scenario.split.pendingOnMain)} pending import`,
      ],
      hint: `${sentences.behind}. ${sentences.pendingOnMain}. ${sentences.action}`,
      name: `Commits, ${sentences.behind}, ${sentences.pendingOnMain}`,
    };
  }
  const sentence = getPendingSentence(scenario);
  if (sentence && scenario.count) {
    const term = scenario.meaning === "rebase" ? "behind" : "pending import";
    return {
      words: [`${formatNumberDisplay(scenario.count)} ${term}`],
      hint: `${sentence}. ${scenario.action}`,
      name: `Commits, ${sentence}`,
    };
  }
  if (scenario.warning) {
    return {
      words: [scenario.warning.label],
      hint: scenario.warning.hint,
      name: `Commits, ${scenario.warning.label}`,
    };
  }
  return null;
}

function CommitsTab({ scenario, to, scrollIntoViewOnActive }: CommitsTabProps) {
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
      {signal?.words.map((words) => (
        <span
          key={words}
          aria-hidden="true"
          className="inline-flex items-center gap-1.5 font-normal"
        >
          <span className="text-subtle-muted">·</span>
          <span className="text-warning tabular-nums">{words}</span>
        </span>
      ))}
    </HintedTab>
  );
}

export function WordsRev01({ scenario }: { scenario: string }) {
  return (
    <ProtoStage
      scenarioOption={scenario}
      renderCommitsTab={(props) => <CommitsTab {...props} />}
      showSplit
    />
  );
}
