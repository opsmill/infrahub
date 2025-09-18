import { Icon } from "@iconify-icon/react";
import { Command, useCommandState } from "cmdk";
import { format } from "date-fns";
import type { ReactElement } from "react";

import { SEARCH_QUERY_NAME } from "@/config/constants";

import useQuery from "@/shared/api/graphql/useQuery";
import { SearchAnywhereGroup } from "@/shared/components/search/search-anywhere-group";
import { SearchAnywhereItem } from "@/shared/components/search/search-anywhere-item";
import { Skeleton } from "@/shared/components/skeleton";
import { Badge } from "@/shared/components/ui/badge";
import { useDebounce } from "@/shared/hooks/useDebounce";

import { POOLS_PEER } from "@/entities/ipam/constants";
import { SEARCH } from "@/entities/nodes/api/search";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getSchemaObjectColumns } from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const SearchNodes = () => {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query.trim(), 300);

  const { data, error, loading } = useQuery(SEARCH, {
    skip: !queryDebounced,
    variables: { search: queryDebounced },
  });

  if (query === "") {
    return null;
  }

  if (loading) {
    return (
      <SearchAnywhereGroup heading="Objects">
        <SearchAnywhereItem to="" disabled>
          Loading...
        </SearchAnywhereItem>
      </SearchAnywhereGroup>
    );
  }

  if (error) return null;

  const results = data?.[SEARCH_QUERY_NAME];

  if (!results || results?.count === 0) return null;

  return (
    <SearchAnywhereGroup heading="Objects">
      {results.edges.map(({ node }: NodesOptionsProps) => (
        <NodesOptions key={node.id} node={node} />
      ))}
    </SearchAnywhereGroup>
  );
};

type NodesOptionsProps = {
  node: {
    id: string;
    kind: string;
  };
};

const NodesOptions = ({ node }: NodesOptionsProps) => {
  const { isGeneric, schema } = useSchema(node.kind);
  const {
    data: objectDetailsData,
    isPending,
    error,
  } = useGetObject({
    objectSchema: schema!,
    objectId: node.id,
    getRelationshipsVisible: (rel) => rel,
  });

  if (!schema) return null;

  if (isPending) return <SearchResultNodeSkeleton />;

  if (error) return null;

  if (!objectDetailsData) return <div className="text-sm">No data found for this object</div>;

  const useIpNamespace =
    !isGeneric &&
    schema?.inherit_from?.some((generic) => {
      return POOLS_PEER.includes(generic);
    });

  const columns = getSchemaObjectColumns({
    schema,
    forListView: true,
    limit: useIpNamespace ? 6 : 7,
  });

  const url = getObjectDetailsUrl(objectDetailsData.__typename, objectDetailsData.id);

  return (
    <SearchAnywhereItem to={url} value={url}>
      <Icon
        icon={schema.icon || "mdi:code-braces-box"}
        className="px-2 py-0.5 text-custom-blue-700 text-lg"
      />

      <div className="grow overflow-auto text-sm">
        <div className="flex justify-between">
          <span className="mr-1 font-semibold text-custom-blue-800">
            {getNodeLabel(objectDetailsData)}
          </span>

          <div className="inline-flex items-center gap-1">
            <Badge variant="blue" className="py-0 text-xxs">
              {schema.namespace}
            </Badge>
            <span className="mr-2 font-medium text-xxs">{schema.label}</span>
          </div>
        </div>

        <div className="mt-1 flex gap-5 text-gray-600">
          {useIpNamespace && (
            <NodeAttribute
              title={"IP Namespace"}
              value={{ value: objectDetailsData?.ip_namespace?.node?.display_label }}
            />
          )}

          {columns
            .filter(({ name }) => !["name", "label"].includes(name))
            .map((column) => (
              <NodeAttribute
                key={column.name}
                title={column.label}
                kind={column.kind}
                value={objectDetailsData[column.name]}
              />
            ))}
        </div>
      </div>
    </SearchAnywhereItem>
  );
};

type NodeAttributeProps = {
  title: string;
  kind?: string;
  value:
    | { value: string | number | boolean | null }
    | { value: string | null; label: string; color: string }
    | { node: { display_label?: string } }
    | { edges: Array<{ node: { display_label?: string } }> };
};

const NodeAttribute = ({ title, kind, value }: NodeAttributeProps) => {
  const formatValue = (): string | number | boolean | ReactElement | null => {
    if ("node" in value && value.node) {
      return value.node.display_label ?? null;
    }

    if ("edges" in value && value.edges?.length > 0) {
      return value.edges.map(({ node }) => node?.display_label).join(", ");
    }

    if ("value" in value && value.value) {
      switch (kind) {
        case ATTRIBUTE_KIND.BOOLEAN:
          return <Icon icon={value.value ? "mdi:check" : "mdi:remove"} className="text-sm" />;
        case ATTRIBUTE_KIND.COLOR:
          return (
            <div
              className="mt-0.5 h-4 w-4 rounded-sm"
              style={{ background: value.value as string }}
            />
          );
        case ATTRIBUTE_KIND.DATETIME: {
          const date = typeof value.value === "string" ? new Date(value.value) : new Date();
          return format(date, "yyyy/MM/dd HH:mm");
        }
        case ATTRIBUTE_KIND.DROPDOWN: {
          if (!("color" in value)) return value.value;

          const color = value.color === "" ? "#f1f1f1" : value.color;
          return (
            <div
              className="truncate rounded-sm border border-transparent px-1.5 text-center font-medium text-gray-700"
              style={{ background: `${color}40` }}
            >
              {value.label}
            </div>
          );
        }
      }
      return value.value;
    }

    return null;
  };

  return (
    <div className="flex flex-col overflow-hidden whitespace-nowrap text-xxs leading-3">
      <span>{title}</span>
      <span className="truncate font-medium text-gray-800">{formatValue() || "-"}</span>
    </div>
  );
};

export const SearchResultNodeSkeleton = () => {
  return (
    <Command.Item disabled className="flex w-full py-2">
      <Skeleton className="mx-1 mr-2 h-6 w-6 rounded-sm" />

      <div className="grow space-y-2">
        <div className="flex space-x-2">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-3 w-20" />
        </div>
        <div className="space-y-1">
          <Skeleton className="h-3 max-w-xl" />
          <Skeleton className="h-3 max-w-xl" />
        </div>
      </div>
    </Command.Item>
  );
};
