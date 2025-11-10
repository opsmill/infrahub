import React from "react";
import { ListBox } from "react-aria-components";

import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { classNames } from "@/shared/utils/common";

import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";
import { useGetProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { ProposedChangesItemLight } from "@/entities/proposed-changes/ui/proposed-change-item-light";
import { ProposedChangesTableSkeleton } from "@/entities/proposed-changes/ui/proposed-changes-table-skeleton";
import type { NodeSchema } from "@/entities/schema/types";

import { ProposedChangesTableHeader } from "./proposed-changes-table-header";

type ProposedChangesTableHomepageProps = {
  schema: NodeSchema;
  className?: string;
};

export function ProposedChangesTableHomepage({
  schema,
  className,
}: ProposedChangesTableHomepageProps) {
  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useGetProposedChanges(
    {
      schema,
    }
  );

  const isLoading = isPending || isFetchingNextPage;

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage} className="h-full">
      <ProposedChangesTableHeader />

      <ListBox
        aria-label="Proposed changes list"
        items={flatData}
        className={classNames(
          "m-2 flex flex-col divide-y divide-gray-200 rounded-lg border border-gray-200",
          className
        )}
      >
        {(node) => <ProposedChangesItemLight key={node.id} node={node} />}
      </ListBox>

      {!isLoading && flatData.length === 0 && (
        <EmptyHomeCard
          className="py-20"
          title={"You don’t have any open proposed changes"}
          subtitle={"Once you create or review a branch, changes will appear here."}
        />
      )}

      {isLoading && <ProposedChangesTableSkeleton headerCount={flatData.length} />}
    </InfiniteScroll>
  );
}
