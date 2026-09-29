// PROTOTYPE — "Object layout" direction: same layers, cards and colours as the object details page
// (Content.Card → header row → tabs → body Card → DetailsLayout → Cards with CardHeader).
import { Card, CardHeader } from "@infrahub/ui";

import { DetailsLayout } from "@/shared/components/layout/details-layout";
import { classNames } from "@/shared/utils/common";

import { computeReadiness } from "./data";
import { GitRepositoriesCard } from "./git-repositories-card";
import { describe, IssueLinks, issueKey, MergeGate, TONES, VerdictIcon } from "./merge-rail";
import { Attributes, type VariantProps } from "./shared";
import { TasksTable } from "./tasks-table";

export function ObjectVariant({
  data,
  locate,
  onLocate,
  card,
  tasksPage,
  onTasksPage,
}: VariantProps) {
  const readiness = computeReadiness(data);
  const { branch } = data;

  return (
    <DetailsLayout>
      <DetailsLayout.Main>
        <Attributes branch={branch} title="Details" />
        <GitRepositoriesCard
          {...card}
          objectStyle
          data={data}
          locate={locate}
          onLocate={onLocate}
        />
        <TasksTable
          objectStyle
          tasks={data.tasks}
          page={tasksPage}
          onPageChange={onTasksPage}
          locate={locate}
          unavailable={data.tasksUnknown}
        />
      </DetailsLayout.Main>

      <DetailsLayout.Aside className="xl:sticky xl:top-0">
        <MergeCard readiness={readiness} branchName={branch.name} onLocate={onLocate} />
      </DetailsLayout.Aside>
    </DetailsLayout>
  );
}

function MergeCard({
  readiness,
  branchName,
  onLocate,
}: {
  readiness: ReturnType<typeof computeReadiness>;
  branchName: string;
  onLocate: VariantProps["onLocate"];
}) {
  const { tone, title, sub } = describe(readiness);
  return (
    <Card aria-label="Merge readiness" role="region">
      <CardHeader>Merge</CardHeader>
      <div className="flex flex-col gap-3 p-3">
        <div className={classNames("flex items-start gap-2 rounded-lg border p-3", TONES[tone])}>
          <span className="mt-0.5 shrink-0">
            <VerdictIcon readiness={readiness} />
          </span>
          <div className="min-w-0">
            <div className="font-semibold text-neutral-900 text-sm">{title}</div>
            {sub && <p className="text-pretty text-neutral-600 text-xs">{sub}</p>}
          </div>
        </div>
        <IssueLinks readiness={readiness} onLocate={onLocate} />
        <MergeGate key={issueKey(readiness)} readiness={readiness} branchName={branchName} />
      </div>
    </Card>
  );
}
