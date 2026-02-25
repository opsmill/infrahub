import { Icon } from "@iconify-icon/react";
import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import Content from "@/shared/components/layout/content";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjects } from "@/entities/nodes/object/domain/get-objects";
import { getObjectTableColumns } from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import type { SearchResultItem } from "@/entities/search-results/types";

type SearchResultsGroupProps = {
  kind: string;
  results: SearchResultItem[];
  isOpen: boolean;
  onToggle: () => void;
};

export function SearchResultsGroup({ kind, results, isOpen, onToggle }: SearchResultsGroupProps) {
  const { schema } = useSchema(kind);
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  const ids = results.map((r) => r.id);

  const { data, isPending } = useQuery({
    queryKey: ["search-group-objects", currentBranch.name, atDate, kind, ids],
    queryFn: () =>
      getObjects({
        schema: schema!,
        branchName: currentBranch.name,
        atDate,
        filters: [{ name: "ids", value: ids.map((id) => ({ id })) }],
        limit: ids.length,
        offset: 0,
      }),
    enabled: !!schema && isOpen,
  });

  if (!schema) return null;

  const label = schema.label || schema.name || kind;
  const columns = getObjectTableColumns(schema);

  return (
    <Content.Card className="flex flex-col">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="flex w-full items-center gap-3 border-gray-200 p-5 text-left hover:bg-gray-50"
        style={{ borderBottomWidth: isOpen ? 1 : 0 }}
      >
        <Icon
          icon={isOpen ? "mdi:chevron-down" : "mdi:chevron-right"}
          className="text-gray-400 text-lg"
        />
        <span className="font-bold text-xl">{label}</span>
        <span className="rounded-full bg-custom-blue-700/10 px-2.5 py-0.5 text-custom-blue-700 text-sm">
          {results.length}
        </span>
      </button>

      {isOpen && (
        <InfiniteScroll scrollX hasNextPage={false} onLoadMore={() => {}}>
          <DataTable
            columns={columns}
            count={results.length}
            data={data ?? []}
            isLoading={isPending}
          />
        </InfiniteScroll>
      )}
    </Content.Card>
  );
}
