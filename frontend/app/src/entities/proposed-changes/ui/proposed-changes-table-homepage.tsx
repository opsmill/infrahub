import React from "react";
import { ListBox } from "react-aria-components";

import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { classNames } from "@/shared/utils/common";

import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import type { Permission } from "@/entities/permission/types";
import { useGetProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { ProposedChangesItemLight } from "@/entities/proposed-changes/ui/proposed-change-item-light";
import { ProposedChangesTableSkeleton } from "@/entities/proposed-changes/ui/proposed-changes-table-skeleton";
import type { NodeSchema } from "@/entities/schema/types";

type ProposedChangesTableHomepageProps = {
  schema: NodeSchema;
  permission: Permission;
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
      <ListBox
        aria-label="Branches list"
        items={flatData}
        className={classNames(
          "m-2 flex flex-col divide-y divide-gray-200 rounded-lg border border-gray-200",
          className
        )}
      >
        {flatData.map((node) => {
          return <ProposedChangesItemLight key={node.id} node={node} />;
        })}
      </ListBox>

      {!isLoading && flatData.length === 0 && <ObjectTableEmpty schema={schema} />}

      {isLoading && <ProposedChangesTableSkeleton headerCount={flatData.length} />}
    </InfiniteScroll>
  );
}
