// PROTOTYPE — "Consistent" direction: every list is the same paginated table, actions live in the
// header menu, and a compact rail holds the verdict, links to each issue, and the merge gate.
import { Col } from "@/shared/components/container";

import { computeReadiness } from "./data";
import { GitRepositoriesCard } from "./git-repositories-card";
import { MergeRail } from "./merge-rail";
import { Attributes, type VariantProps } from "./shared";
import { TasksTable } from "./tasks-table";

export function ConsistentVariant({
  data,
  locate,
  onLocate,
  card,
  tasksPage,
  onTasksPage,
  railWidth,
}: VariantProps) {
  const readiness = computeReadiness(data);

  return (
    <div className="@container p-3">
      <div
        className="grid @min-[1100px]:grid-cols-[minmax(0,1fr)_var(--rail-width)] items-start gap-4"
        style={{ "--rail-width": `${railWidth}px` } as React.CSSProperties}
      >
        <div className="@min-[1100px]:sticky @min-[1100px]:top-3 @min-[1100px]:col-start-2 @min-[1100px]:row-start-1">
          <MergeRail readiness={readiness} branchName={data.branch.name} onLocate={onLocate} />
        </div>
        <Col className="@min-[1100px]:col-start-1 @min-[1100px]:row-start-1 min-w-0 gap-3">
          <Attributes branch={data.branch} />
          <GitRepositoriesCard {...card} data={data} locate={locate} onLocate={onLocate} />
          <TasksTable
            tasks={data.tasks}
            page={tasksPage}
            onPageChange={onTasksPage}
            locate={locate}
            unavailable={data.tasksUnknown}
          />
        </Col>
      </div>
    </div>
  );
}
