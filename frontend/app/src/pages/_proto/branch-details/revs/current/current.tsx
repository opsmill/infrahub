// PROTOTYPE — "Current": today's branch details page, with none of this design's changes.
// The baseline every direction is compared against. Frozen: never import from another revision.
// Real presentational pieces (BranchAttributes, task badges, LinkTab styling); buttons and the task
// list are static replicas, because the real ones call the backend (Merge would send a merge).
import { Button, LinkButton } from "@infrahub/ui";
import { CheckIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "react-toastify";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { Col, Row } from "@/shared/components/container";
import Accordion from "@/shared/components/display/accordion";
import { DateDisplay } from "@/shared/components/display/date-display";
import Content from "@/shared/components/layout/content";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import type { BranchDetail } from "@/entities/branches/domain/model/branch";
import { BranchAttributes } from "@/entities/branches/ui/branch-details/branch-attributes";
import { getLogBadge } from "@/entities/tasks/ui/task-display";

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

const BRANCH = {
  id: "proto-branch",
  name: "ple-emea-fabric-expansion-ams1-phase-2-leaf-spine-upgrade",
  description: "Adds 12 leaf switches in AMS1 hall 3 and regenerates the fabric underlay.",
  origin_branch: "main",
  branched_from: ago(2 * 24 * 60),
  created_at: ago(6 * 24 * 60),
  status: BranchStatus.OPEN,
  sync_with_git: true,
  is_default: false,
  schema_differs_from_default_branch: false,
} as unknown as BranchDetail;

// Today's Tasks accordion only shows the validate, merge and rebase workflows.
const TASKS = [
  { id: "t1", title: "Validate branch", state: "COMPLETED", updated_at: ago(30) },
  { id: "t2", title: "Rebase branch", state: "COMPLETED", updated_at: ago(2 * 24 * 60) },
];

const TASK_BG: Record<string, string> = { COMPLETED: "bg-green-700/10", FAILED: "bg-red-100" };

const TABS = ["Details", "Data", "Files", "Artifacts", "Schema"] as const;

const info = (m: string) => toast(<Alert type={ALERT_TYPES.INFO} message={`${m} (prototype)`} />);

export function CurrentPage() {
  const [tab, setTab] = useState<string>("Details");

  return (
    <Content.Card>
      <div className="flex items-center gap-2 border-custom-blue-700/15 border-b bg-custom-blue-700/5 px-5 py-2 text-custom-blue-700 text-sm">
        You're working on this branch.
      </div>

      <header className="p-5 pb-2">
        <Row>
          <h1 className="font-bold text-xl">{BRANCH.name}</h1>
        </Row>
        <p className="text-sm">{BRANCH.description}</p>
      </header>

      <nav aria-label="Tabs">
        <Row className="border-gray-200 border-b">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              aria-current={t === tab ? "page" : undefined}
              className={classNames(
                "transition-all focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25",
                "inline-flex h-11 items-center gap-2 truncate border-transparent border-b-2 px-3 py-2 font-medium text-sm",
                t === tab
                  ? "border-custom-blue-600 text-custom-blue-600"
                  : "text-gray-500 hover:border-gray-300 hover:text-gray-700"
              )}
            >
              {t}
            </button>
          ))}
        </Row>
      </nav>

      <div className="p-2">
        {tab !== "Details" ? (
          <div className="flex h-60 items-center justify-center text-neutral-500 text-sm">
            {tab} tab, as today.
          </div>
        ) : (
          <Col>
            <BranchAttributes branch={BRANCH} />
            <Col>
              <Row className="flex-wrap">
                <Button
                  variant="active"
                  className="flex items-center gap-2"
                  onPress={() => info("Merge")}
                >
                  Merge
                  <CheckIcon className="size-4" />
                </Button>
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
              <Accordion title={<div className="py-2 font-normal text-xs">Tasks</div>}>
                <Col className="gap-2">
                  {TASKS.map((t) => (
                    <div
                      key={t.id}
                      className={classNames(
                        "m-auto flex w-full flex-col gap-4 rounded-md p-4",
                        TASK_BG[t.state]
                      )}
                    >
                      <div className="flex justify-between">
                        <div className="flex items-center gap-4">
                          {getLogBadge[t.state]}
                          {t.title}
                        </div>
                        <DateDisplay date={t.updated_at} />
                      </div>
                    </div>
                  ))}
                </Col>
              </Accordion>
            </Col>
          </Col>
        )}
      </div>
    </Content.Card>
  );
}
