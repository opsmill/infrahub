import { Col, Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";

import type { PendingMerge } from "@/entities/repository/domain/model/repository-push-state";

interface PendingMergeListProps {
  merges: PendingMerge[];
}

export function PendingMergeList({ merges }: PendingMergeListProps) {
  return (
    <Col className="w-0 min-w-full gap-1.5">
      {merges.map((merge) => (
        <Row key={merge.entry_id}>
          <span
            className="min-w-0 flex-1 truncate font-medium text-foreground"
            title={merge.source_branch}
          >
            {merge.source_branch}
          </span>
          <code className="text-foreground-muted text-xs">{merge.source_commit.slice(0, 7)}</code>
          <DateDisplay date={merge.merged_at} className="text-foreground-muted" />
        </Row>
      ))}
    </Col>
  );
}
