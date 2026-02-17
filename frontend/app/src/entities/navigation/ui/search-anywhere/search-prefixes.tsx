import { Icon } from "@iconify-icon/react";
import { Command, useCommandState } from "cmdk";

import { Skeleton } from "@/shared/components/loading/skeleton";
import { Badge } from "@/shared/components/ui/badge";
import { useDebounce } from "@/shared/hooks/useDebounce";

import type { ObjectResult } from "@/entities/navigation/domain/search-anywhere";
import { useGetSearchAnywhere } from "@/entities/navigation/domain/search-anywhere.query";
import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";
import { SearchAnywhereItem } from "@/entities/navigation/ui/search-anywhere/search-anywhere-item";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const SearchPrefixes = () => {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query.trim(), 300);

  const { data, isPending, error } = useGetSearchAnywhere(
    { search: queryDebounced },
    {
      enabled: !!queryDebounced,
    }
  );

  if (query === "") {
    return null;
  }

  if (!data?.isPrefixLookup) {
    return null;
  }

  if (isPending) {
    return (
      <SearchAnywhereGroup heading="Parent Prefixes">
        <SearchAnywhereItem to="" disabled>
          Loading...
        </SearchAnywhereItem>
      </SearchAnywhereGroup>
    );
  }

  if (error) return null;

  if (data.count === 0) return null;

  return (
    <SearchAnywhereGroup heading="Parent Prefixes">
      {data.matchingObjects.map((node) => (
        <PrefixOption key={node.id} node={node} searchQuery={queryDebounced} />
      ))}
    </SearchAnywhereGroup>
  );
};

type PrefixOptionProps = {
  node: ObjectResult;
  searchQuery: string;
};

const PrefixOption = ({ node, searchQuery }: PrefixOptionProps) => {
  const { schema } = useSchema(node.kind);
  const {
    data: objectDetailsData,
    isPending,
    error,
  } = useGetObject({
    objectSchema: schema!,
    objectId: node.id,
    getRelationshipsVisible: (relationships) =>
      relationships.filter((rel) => rel.cardinality === "one"),
  });

  if (!schema) return null;

  if (isPending) return <SearchResultPrefixSkeleton />;

  if (error) return null;

  if (!objectDetailsData) return null;

  const url = getObjectDetailsUrl(objectDetailsData.__typename, objectDetailsData.id);
  const prefix = objectDetailsData.prefix as { value: string } | undefined;
  const prefixValue = prefix?.value ?? "";
  const isExactMatch = prefixValue === searchQuery;
  const ipNamespace = objectDetailsData.ip_namespace as { node: NodeCore | null } | undefined;
  const namespaceName = ipNamespace?.node ? getNodeLabel(ipNamespace.node) : null;

  return (
    <SearchAnywhereItem to={url} value={url}>
      <Icon
        icon={schema.icon || "mdi:ip-network"}
        className="px-2 py-0.5 text-custom-blue-700 text-lg"
      />

      <div className="grow overflow-auto text-sm">
        <div className="flex items-center justify-between">
          <span className="mr-1 font-semibold text-custom-blue-800">
            {prefixValue || getNodeLabel(objectDetailsData)}
          </span>

          <div className="inline-flex items-center gap-1">
            {isExactMatch && (
              <Badge variant="green" className="py-0 text-xxs">
                Exact match
              </Badge>
            )}
            {namespaceName && (
              <Badge variant="blue" className="py-0 text-xxs">
                {namespaceName}
              </Badge>
            )}
            <span className="mr-2 font-medium text-xxs">{schema.label}</span>
          </div>
        </div>
      </div>
    </SearchAnywhereItem>
  );
};

const SearchResultPrefixSkeleton = () => {
  return (
    <Command.Item disabled className="flex w-full py-2">
      <Skeleton className="mx-1 mr-2 h-6 w-6 rounded-sm" />
      <div className="grow space-y-2">
        <div className="flex space-x-2">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
    </Command.Item>
  );
};
