import { useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import Content from "@/shared/components/layout/content";
import { DataTable } from "@/shared/components/table/data-table";
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/shared/components/ui/accordion";
import { InfiniteTrigger } from "@/shared/components/utils/infinite-trigger";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjects } from "@/entities/nodes/object/domain/get-objects";
import { getObjectTableColumns } from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import type { SearchResultItem } from "@/entities/search-results/types";

type SearchResultsGroupProps = {
  kind: string;
  results: SearchResultItem[];
};

export function SearchResultsGroup({ kind, results }: SearchResultsGroupProps) {
  const { schema } = useSchema(kind);
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  const ids = results.map((r) => r.id);

  const { data, isPending, hasNextPage, fetchNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ["search-group-objects", currentBranch.name, atDate, kind, ids],
    queryFn: ({ pageParam }: { pageParam: { offset: number; limit: number } }) => {
      const pageIds = ids.slice(pageParam.offset, pageParam.offset + pageParam.limit);
      return getObjects({
        schema: schema!,
        branchName: currentBranch.name,
        atDate,
        filters: [{ name: "ids", value: pageIds.map((id) => ({ id })) }],
        limit: pageIds.length,
        offset: 0,
      });
    },
    initialPageParam: { offset: 0, limit: DEFAULT_PAGE_SIZE },
    getNextPageParam: (_lastPage, _allPages, lastPageParam) => {
      const nextOffset = lastPageParam.offset + lastPageParam.limit;
      if (nextOffset >= ids.length) return undefined;
      return { offset: nextOffset, limit: DEFAULT_PAGE_SIZE };
    },
    enabled: !!schema,
  });

  if (!schema) return null;

  const label = schema.label || schema.name || kind;
  const columns = getObjectTableColumns(schema);

  const flatData = data?.pages.flat() ?? [];
  const skeletonRowCount = Math.min(results.length, DEFAULT_PAGE_SIZE);

  return (
    <AccordionItem value={kind} asChild>
      <Content.Card className="flex flex-col">
        <AccordionTrigger
          className="sticky top-0 z-10 gap-2 border-gray-200 bg-white px-4 py-3 text-sm hover:bg-gray-50 data-[state=open]:border-b"
          iconClassName="-order-1 ml-0"
        >
          <span className="font-semibold text-sm">{label}</span>
          <span className="rounded-full bg-custom-blue-700/10 px-1.5 py-0.5 text-custom-blue-700 text-xs">
            {results.length}
          </span>
        </AccordionTrigger>

        <AccordionContent>
          <div className="max-h-[50vh] overflow-auto">
            <DataTable
              columns={columns}
              count={results.length}
              data={flatData}
              isLoading={isPending || isFetchingNextPage}
              skeletonRowCount={skeletonRowCount}
            />
            <InfiniteTrigger
              hasNextPage={hasNextPage}
              onLoadMore={fetchNextPage}
              isFetchingNextPage={isFetchingNextPage}
            />
          </div>
        </AccordionContent>
      </Content.Card>
    </AccordionItem>
  );
}
