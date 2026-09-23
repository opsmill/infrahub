// PROTOTYPE — "Legacy" direction: today's page shape (attributes, button row, Tasks accordion of
// cards) with the IFC-3200 repositories card and the merge gate folded into it.
import { Button, Checkbox, LinkButton } from "@infrahub/ui";
import { CheckIcon, LockIcon } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "react-toastify";

import { Col, Row } from "@/shared/components/container";
import Accordion from "@/shared/components/display/accordion";
import { DateDisplay } from "@/shared/components/display/date-display";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import { computeReadiness, type TaskRow } from "./data";
import { GitRepositoriesCard } from "./git-repositories-card";
import { taskDomId, useLocate } from "./locate";
import { describe, fakeMerge, IssueLinks, issueKey, TONES, VerdictIcon } from "./merge-rail";
import { Attributes, type VariantProps } from "./shared";
import { STATE_BADGE, TaskLogLines } from "./tasks-table";

const info = (m: string) => toast(<Alert type={ALERT_TYPES.INFO} message={`${m} (prototype)`} />);

const CARD_BG: Record<TaskRow["state"], string> = {
  COMPLETED: "bg-green-700/10",
  FAILED: "bg-red-100",
  RUNNING: "bg-gray-100",
};

export function LegacyVariant(props: VariantProps) {
  const { data, locate, onLocate } = props;
  const readiness = computeReadiness(data);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [openLogs, setOpenLogs] = useState<Set<string>>(new Set());

  useLocate(locate, "task", (id) => {
    if (!data.tasks.some((t) => t.id === id)) return null;
    setTasksOpen(true);
    setOpenLogs((prev) => new Set(prev).add(id));
    return taskDomId(id);
  });

  return (
    <Col className="gap-3 p-2">
      <Attributes branch={data.branch} />
      <GitRepositoriesCard {...props.card} data={data} locate={locate} onLocate={onLocate} />

      <LegacyMergeRow
        key={issueKey(readiness)}
        readiness={readiness}
        branchName={data.branch.name}
        onLocate={onLocate}
      />

      <Accordion
        open={tasksOpen}
        onOpenChange={setTasksOpen}
        title={
          <div className="py-2 font-normal text-xs">
            Tasks <span className="text-neutral-500 tabular-nums">({data.tasks.length})</span>
          </div>
        }
      >
        <Col className="gap-2">
          {data.tasks.map((t) => (
            <div
              key={t.id}
              id={taskDomId(t.id)}
              tabIndex={-1}
              className={classNames(
                "flex flex-col gap-3 rounded-md p-4 outline-offset-[-2px]",
                CARD_BG[t.state]
              )}
            >
              <div className="flex justify-between gap-4 text-sm">
                <div className="flex min-w-0 items-center gap-4">
                  {STATE_BADGE[t.state]}
                  <span className="truncate" title={t.title}>
                    {t.title}
                  </span>
                  <span className="truncate text-neutral-600 text-xs">{t.related}</span>
                </div>
                <DateDisplay date={t.updatedAt} />
              </div>
              <Accordion
                open={openLogs.has(t.id)}
                onOpenChange={(o) =>
                  setOpenLogs((prev) => {
                    const next = new Set(prev);
                    if (o) next.add(t.id);
                    else next.delete(t.id);
                    return next;
                  })
                }
                title={<div className="font-normal text-xs">Logs</div>}
              >
                <div className="mt-2 rounded bg-white/60 p-2">
                  <TaskLogLines logs={t.logs} />
                </div>
              </Accordion>
            </div>
          ))}
        </Col>
      </Accordion>
    </Col>
  );
}

function LegacyMergeRow({
  readiness,
  branchName,
  onLocate,
}: {
  readiness: ReturnType<typeof computeReadiness>;
  branchName: string;
  onLocate: VariantProps["onLocate"];
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const reasonId = useId();
  const { tone, title, sub, ack } = describe(readiness);
  const gated = readiness.verdict === "blocked" || readiness.verdict === "warn";
  const blocked = readiness.verdict === "blocked";

  return (
    <Col className="gap-2">
      {gated && (
        <div
          role="status"
          className={classNames("flex flex-col gap-2 rounded-lg border p-3", TONES[tone])}
        >
          <div className="flex items-start gap-2">
            <span className="mt-0.5 shrink-0">
              <VerdictIcon readiness={readiness} />
            </span>
            <div>
              <div className="font-semibold text-neutral-900 text-sm">{title}</div>
              {sub && <p className="text-neutral-600 text-xs">{sub}</p>}
            </div>
          </div>
          <IssueLinks readiness={readiness} onLocate={onLocate} />
          <Checkbox isSelected={acknowledged} onChange={setAcknowledged} className="items-start">
            <span id={reasonId} className="text-neutral-800 text-sm">
              {ack}
            </span>
          </Checkbox>
        </div>
      )}
      <Row className="flex-wrap">
        {!gated ? (
          <Button
            variant="active"
            className="flex items-center gap-2"
            isDisabled={readiness.verdict === "checking"}
            onPress={() => fakeMerge(branchName)}
          >
            Merge <CheckIcon className="size-4" />
          </Button>
        ) : acknowledged ? (
          <Button variant={blocked ? "danger" : "warning"} onPress={() => fakeMerge(branchName)}>
            Merge anyway
          </Button>
        ) : (
          <Button variant="outline" isDisabled isDisabledAndFocusable aria-describedby={reasonId}>
            <LockIcon className="size-4" aria-hidden /> Merge
          </Button>
        )}
        <LinkButton href="/proposed-changes/new" variant="outline">
          Propose change
        </LinkButton>
        <Button variant="outline" onPress={() => info("Rebase")}>
          Rebase
        </Button>
        <Button variant="outline" onPress={() => info("Validate")}>
          Validate
        </Button>
        <Button variant="danger-outline" onPress={() => info("Delete")}>
          Delete
        </Button>
      </Row>
    </Col>
  );
}
