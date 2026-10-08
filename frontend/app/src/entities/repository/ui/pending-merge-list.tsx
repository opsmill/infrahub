import { DateDisplay } from "@/shared/components/display/date-display";

import type { PendingMerge } from "@/entities/repository/domain/model/delivery-state";

interface PendingMergeListProps {
  merges: PendingMerge[];
}

export function PendingMergeList({ merges }: PendingMergeListProps) {
  return (
    <ol className="flex flex-col gap-1">
      {merges.map((merge) => (
        <li key={merge.entry_id} className="flex items-center gap-2">
          <span className="font-medium">{merge.source_branch}</span>
          <code className="text-xs">{merge.source_commit.slice(0, 7)}</code>
          <DateDisplay date={merge.merged_at} />
        </li>
      ))}
    </ol>
  );
}
