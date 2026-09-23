// PROTOTYPE — merge gate shared by both variants, plus the Consistent variant's compact rail.
// Import Error (sync_status) blocks by default; task results and unknowns warn. Both need an
// explicit acknowledgement to merge anyway.
import { Button, Checkbox, Spinner } from "@infrahub/ui";
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  CheckIcon,
  CircleHelpIcon,
  LoaderIcon,
  LockIcon,
} from "lucide-react";
import { useId, useState } from "react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import type { Readiness } from "./data";
import type { LocateTarget } from "./locate";

export type OnLocate = (target: Omit<LocateTarget, "nonce">) => void;

export function fakeMerge(branchName: string) {
  toast(
    <Alert
      type={ALERT_TYPES.SUCCESS}
      message={`Merge requested for '${branchName}' (prototype, nothing was merged)`}
    />,
    { toastId: "proto-merge" }
  );
}

/** Key that changes whenever the set of problems changes, so an acknowledgement never carries over. */
export function issueKey(readiness: Readiness) {
  if (readiness.verdict === "blocked")
    return [...readiness.blockers.map((b) => b.key), ...readiness.warnings.map((w) => w.key)].join(
      "|"
    );
  if (readiness.verdict === "warn") return readiness.warnings.map((w) => w.key).join("|");
  return readiness.verdict;
}

export type Tone = "red" | "amber" | "blue" | "neutral" | "plain";

export function describe(readiness: Readiness): {
  tone: Tone;
  title: string;
  sub?: string;
  ack?: string;
} {
  switch (readiness.verdict) {
    case "checking":
      return { tone: "neutral", title: "Checking repositories…" };
    case "clear":
      return readiness.empty
        ? {
            tone: "plain",
            title: "No Git repositories on this branch",
            sub: "Nothing to import or generate before merging.",
          }
        : {
            tone: "plain",
            title: "Ready to merge",
            sub: "Every repository imported, and the latest generator runs passed.",
          };
    case "blocked": {
      const n = readiness.blockers.length;
      return {
        tone: "red",
        title: "Merge blocked",
        sub: `${n} ${n === 1 ? "repository" : "repositories"} failed to import. Fix the import, then merge.`,
        ack: "I understand. Merge anyway and carry the failed import into the default branch.",
      };
    }
    default: {
      const failed = readiness.warnings.some((w) => w.kind === "failed");
      const running = readiness.warnings.some((w) => w.kind === "running");
      if (failed)
        return {
          tone: "amber",
          title: "Generator runs failed on this branch",
          sub: "This doesn't block the merge. Latest run of each only.",
          ack: "I understand. Artifacts on the default branch may be stale.",
        };
      if (running)
        return {
          tone: "blue",
          title: "Tasks are still running",
          sub: "This doesn't block the merge.",
          ack: "I understand. Merge before these runs finish.",
        };
      return {
        tone: "neutral",
        title: "Couldn't check everything",
        ack: "I understand. Merge without checking.",
      };
    }
  }
}

export const TONES: Record<Tone, string> = {
  red: "border-red-200 bg-red-50",
  amber: "border-amber-200 bg-amber-50",
  blue: "border-custom-blue-700/20 bg-custom-blue-700/5",
  neutral: "border-neutral-200 bg-neutral-50",
  plain: "border-neutral-200 bg-white",
};

export function VerdictIcon({ readiness }: { readiness: Readiness }) {
  const { tone } = describe(readiness);
  if (readiness.verdict === "checking") return <Spinner className="size-4" />;
  if (readiness.verdict === "clear")
    return (
      <CheckIcon
        className={classNames("size-4", readiness.empty ? "text-neutral-500" : "text-green-700")}
        aria-hidden
      />
    );
  if (tone === "red") return <AlertCircleIcon className="size-4 text-red-700" aria-hidden />;
  if (tone === "amber") return <AlertTriangleIcon className="size-4 text-amber-700" aria-hidden />;
  if (tone === "blue")
    return (
      <LoaderIcon
        className="size-4 animate-spin text-custom-blue-700 motion-reduce:animate-none"
        aria-hidden
      />
    );
  return <CircleHelpIcon className="size-4 text-neutral-600" aria-hidden />;
}

type IssueItem = {
  key: string;
  label: string;
  detail: string;
  target: Omit<LocateTarget, "nonce" | "instant"> | null;
  tone: string;
};

function issueItems(readiness: Readiness): IssueItem[] {
  if (readiness.verdict !== "blocked" && readiness.verdict !== "warn") return [];
  const blockers = readiness.verdict === "blocked" ? readiness.blockers : [];
  return [
    ...blockers.map((b) => ({
      key: b.key,
      label: b.repo.name,
      detail: `Import failed: ${b.error.title}`,
      target: { kind: "band" as const, id: b.repo.id },
      tone: "text-red-800",
    })),
    ...readiness.warnings.map((w) => ({
      key: w.key,
      label: w.subject,
      detail: w.detail,
      target: w.taskId ? { kind: "task" as const, id: w.taskId } : null,
      tone: w.kind === "failed" ? "text-amber-800" : "text-neutral-600",
    })),
  ];
}

/** One line per issue, each jumping to where its detail lives (error band or task row). */
export function IssueLinks({ readiness, onLocate }: { readiness: Readiness; onLocate: OnLocate }) {
  const items = issueItems(readiness);
  if (!items.length) return null;
  return (
    <ul className="flex max-h-64 flex-col overflow-y-auto">
      {items.map((it) => (
        <li key={it.key}>
          {it.target ? (
            <button
              type="button"
              onClick={(e) => it.target && onLocate({ ...it.target, instant: e.detail === 0 })}
              className="group flex w-full min-w-0 items-baseline gap-2 rounded-md px-1.5 py-1.5 text-left hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-neutral-500"
            >
              <span className="min-w-0 flex-1">
                <span
                  className="block truncate font-medium text-neutral-900 text-sm"
                  title={it.label}
                >
                  {it.label}
                </span>
                <span className={classNames("block truncate text-xs", it.tone)}>{it.detail}</span>
              </span>
              <span
                className="shrink-0 text-neutral-500 text-xs group-hover:text-neutral-800"
                aria-hidden
              >
                Show ↓
              </span>
            </button>
          ) : (
            <div className="px-1.5 py-1.5">
              <span className="block font-medium text-neutral-900 text-sm">{it.label}</span>
              <span className={classNames("block text-xs", it.tone)}>{it.detail}</span>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Acknowledgement + Merge button. Rendered inside the rail (Consistent) or the banner (Legacy). */
export function MergeGate({
  readiness,
  branchName,
  fullWidth = true,
}: {
  readiness: Readiness;
  branchName: string;
  fullWidth?: boolean;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const reasonId = useId();
  const { ack } = describe(readiness);
  const width = fullWidth ? "w-full justify-center" : "";

  if (readiness.verdict === "checking")
    return (
      <Button variant="active" className={width} isDisabled>
        Merge
      </Button>
    );
  if (readiness.verdict === "clear")
    return (
      <Button variant="active" className={width} onPress={() => fakeMerge(branchName)}>
        Merge <CheckIcon className="size-4" aria-hidden />
      </Button>
    );

  const blocked = readiness.verdict === "blocked";
  return (
    <div className={classNames("flex gap-3", fullWidth ? "flex-col" : "flex-wrap items-center")}>
      <Checkbox isSelected={acknowledged} onChange={setAcknowledged} className="items-start">
        <span id={reasonId} className="text-neutral-800 text-sm">
          {ack}
        </span>
      </Checkbox>
      {acknowledged ? (
        <Button
          variant={blocked ? "danger" : "warning"}
          className={width}
          onPress={() => fakeMerge(branchName)}
        >
          Merge anyway
        </Button>
      ) : (
        <Button
          variant="outline"
          className={width}
          isDisabled
          isDisabledAndFocusable
          aria-describedby={reasonId}
        >
          <LockIcon className="size-4" aria-hidden /> Merge
        </Button>
      )}
    </div>
  );
}

export function MergeRail({
  readiness,
  branchName,
  onLocate,
}: {
  readiness: Readiness;
  branchName: string;
  onLocate: OnLocate;
}) {
  const { tone, title, sub } = describe(readiness);
  return (
    <aside
      aria-label="Merge readiness"
      className={classNames("flex flex-col gap-3 rounded-xl border p-4", TONES[tone])}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0">
          <VerdictIcon readiness={readiness} />
        </span>
        <div className="min-w-0">
          <h2 className="font-semibold text-neutral-900 text-sm">{title}</h2>
          {sub && <p className="text-pretty text-neutral-600 text-xs">{sub}</p>}
        </div>
      </div>
      <IssueLinks readiness={readiness} onLocate={onLocate} />
      <MergeGate key={issueKey(readiness)} readiness={readiness} branchName={branchName} />
    </aside>
  );
}
