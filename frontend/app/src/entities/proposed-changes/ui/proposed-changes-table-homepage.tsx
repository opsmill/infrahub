import { ListBox } from "react-aria-components";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { classNames } from "@/shared/utils/common";

import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";
import { PROPOSED_CHANGE_STATES, STATE_VALUES_FILTER } from "@/entities/proposed-changes/constants";
import { useGetProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { ProposedChangesItemLight } from "@/entities/proposed-changes/ui/proposed-change-item-light";
import { ProposedChangesTableHeader } from "@/entities/proposed-changes/ui/proposed-changes-table-header";
import { ProposedChangesTableSkeleton } from "@/entities/proposed-changes/ui/proposed-changes-table-skeleton";
import type { ModelSchema } from "@/entities/schema/types";

type ProposedChangesTableHomepageProps = {
  schema: ModelSchema;
  className?: string;
};

export function ProposedChangesTableHomepage({
  schema,
  className,
}: ProposedChangesTableHomepageProps) {
  const { data, error, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } =
    useGetProposedChanges({
      schema,
      filters: [{ value: PROPOSED_CHANGE_STATES.opened, name: STATE_VALUES_FILTER }],
    });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const flatData = data?.pages?.flat() ?? [];

  if (flatData.length === 0) {
    return (
      <EmptyHomeCard
        title="You don’t have any open proposed changes"
        subtitle="Once you create or review a branch, changes will appear here."
      />
    );
  }

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <ProposedChangesTableHeader />

      <ListBox
        aria-label="Proposed changes list"
        items={flatData}
        className={classNames("flex flex-col divide-y divide-gray-200", className)}
      >
        {(proposedChange) => (
          <ProposedChangesItemLight key={proposedChange.id} proposedChange={proposedChange} />
        )}
      </ListBox>

      {isFetchingNextPage && <ProposedChangesTableSkeleton headerCount={flatData.length} />}
    </InfiniteScroll>
  );
}
