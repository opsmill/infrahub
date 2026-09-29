// PROTOTYPE — branch + repository tasks as a paginated table, same shell as the repositories table.
import { Button, Card, CardHeader, LinkButton } from "@infrahub/ui";
import { ChevronDownIcon, ChevronRightIcon, ExternalLinkIcon, ListChecksIcon } from "lucide-react";
import { Fragment, useState } from "react";

import { DateDisplay } from "@/shared/components/display/date-display";
import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import type { TaskLog, TaskRow, TaskState } from "./data";
import { type LocateTarget, taskDomId, useLocate } from "./locate";
import {
  CELL_HEIGHT_PX,
  clampPage,
  getTotalPages,
  PAGE_SIZE,
  TablePagination,
} from "./table-pagination";

export const STATE_BADGE: Record<TaskState, React.ReactNode> = {
  COMPLETED: <Badge variant="green-outline">COMPLETED</Badge>,
  FAILED: <Badge variant="red-outline">FAILED</Badge>,
  RUNNING: <Badge variant="blue-outline">RUNNING</Badge>,
};

const SEVERITY: Record<TaskLog["severity"], string> = {
  info: "text-neutral-500",
  warning: "text-amber-700",
  error: "text-red-700",
};

export function TaskLogLines({ logs }: { logs: TaskLog[] }) {
  return (
    <ol className="flex flex-col gap-1 font-mono text-xs">
      {logs.map((l, i) => (
        <li key={i} className="flex gap-3">
          <span className={classNames("w-14 shrink-0 uppercase", SEVERITY[l.severity])}>
            {l.severity}
          </span>
          <span className="break-words text-neutral-800">{l.message}</span>
        </li>
      ))}
    </ol>
  );
}

export function TasksTable({
  tasks,
  page,
  onPageChange,
  locate,
  unavailable,
  objectStyle = false,
}: {
  objectStyle?: boolean;
  tasks: TaskRow[];
  page: number;
  onPageChange: (page: number) => void;
  locate: LocateTarget | null;
  unavailable: boolean;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const totalPages = getTotalPages(tasks.length, PAGE_SIZE);
  const currentPage = clampPage(page, totalPages);
  const rows = tasks.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const failed = tasks.filter((t) => t.state === "FAILED").length;

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  useLocate(locate, "task", (id) => {
    const index = tasks.findIndex((t) => t.id === id);
    if (index < 0) return null;
    onPageChange(Math.floor(index / PAGE_SIZE) + 1);
    setExpanded((prev) => new Set(prev).add(id));
    return taskDomId(id);
  });

  return (
    <Card className="overflow-hidden p-0">
      {objectStyle ? (
        <CardHeader className="flex items-center gap-2">
          <h2>Tasks</h2>
          <Badge variant="blue" className="rounded-full font-normal tabular-nums">
            {tasks.length}
          </Badge>
          {failed > 0 && (
            <span className="font-normal text-red-700 text-xs tabular-nums">{failed} failed</span>
          )}
          <LinkButton
            href="/tasks"
            variant="ghost"
            size="xs"
            className="ml-auto h-auto pr-0 text-xs"
          >
            Open in Tasks <ExternalLinkIcon className="size-3" aria-hidden />
          </LinkButton>
        </CardHeader>
      ) : (
        <header className="flex items-center gap-2 px-4 py-3">
          <ListChecksIcon className="size-4 text-neutral-500" aria-hidden />
          <h2 className="font-semibold text-sm">Tasks</h2>
          <span className="rounded-full bg-neutral-100 px-1.5 text-neutral-600 text-xs tabular-nums">
            {tasks.length}
          </span>
          {failed > 0 && <span className="text-red-700 text-xs tabular-nums">{failed} failed</span>}
          <LinkButton href="/tasks" variant="ghost" size="xs" className="ml-auto">
            Open in Tasks <ExternalLinkIcon className="size-3" aria-hidden />
          </LinkButton>
        </header>
      )}

      {unavailable ? (
        <p className="border-neutral-200 border-t px-4 py-4 text-neutral-600 text-sm">
          Task results didn't load. Generator and artifact runs can't be shown.
        </p>
      ) : (
        <>
          <div
            className="overflow-x-auto"
            style={totalPages > 1 ? { minHeight: (PAGE_SIZE + 1) * CELL_HEIGHT_PX } : undefined}
          >
            <table className="w-full min-w-[760px] table-fixed text-sm">
              <thead className="bg-neutral-50 text-left text-neutral-600 text-xs">
                <tr className="h-10 border-neutral-200 border-y">
                  <th className="w-10">
                    <span className="sr-only">Logs</span>
                  </th>
                  <th className="px-3 font-medium">Title</th>
                  <th className="w-[124px] px-3 font-medium">State</th>
                  <th className="w-[110px] px-3 font-medium">Workflow</th>
                  <th className="w-[26%] px-3 font-medium">Related</th>
                  <th className="w-[130px] px-3 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => {
                  const isOpen = expanded.has(t.id);
                  return (
                    <Fragment key={t.id}>
                      <tr
                        id={taskDomId(t.id)}
                        tabIndex={-1}
                        className={classNames(
                          "h-10 scroll-mt-4 border-neutral-200 border-b outline-offset-[-2px]",
                          t.state === "FAILED" && "bg-red-50/40"
                        )}
                      >
                        <td className="px-1 text-center">
                          <Button
                            variant="ghost"
                            size="xs"
                            shape="square"
                            aria-expanded={isOpen}
                            aria-label={`${isOpen ? "Hide" : "Show"} logs for ${t.title}`}
                            onPress={() => toggle(t.id)}
                          >
                            {isOpen ? (
                              <ChevronDownIcon className="size-3.5" />
                            ) : (
                              <ChevronRightIcon className="size-3.5" />
                            )}
                          </Button>
                        </td>
                        <td className="truncate px-3" title={t.title}>
                          {t.title}
                        </td>
                        <td className="px-3">{STATE_BADGE[t.state]}</td>
                        <td className="px-3 text-neutral-600">{t.workflow}</td>
                        <td className="truncate px-3 text-neutral-600" title={t.related}>
                          {t.related}
                        </td>
                        <td className="px-3 text-[13px] text-neutral-600">
                          <DateDisplay date={t.updatedAt} />
                        </td>
                      </tr>
                      {isOpen && (
                        <tr className="border-neutral-200 border-b bg-neutral-50">
                          <td />
                          <td colSpan={5} className="px-3 py-2">
                            <TaskLogLines logs={t.logs} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <TablePagination
              className="border-neutral-200 border-t"
              page={currentPage}
              pageSize={PAGE_SIZE}
              totalCount={tasks.length}
              onPageChange={onPageChange}
            />
          )}
        </>
      )}
    </Card>
  );
}
