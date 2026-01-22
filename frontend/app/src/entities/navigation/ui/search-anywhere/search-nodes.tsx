import { Icon } from "@iconify-icon/react";
import { Command, useCommandState } from "cmdk";
import { format } from "date-fns";
import { useAtomValue } from "jotai";
import type { ReactElement } from "react";

import { Skeleton } from "@/shared/components/loading/skeleton";
import { Badge } from "@/shared/components/ui/badge";
import { useDebounce } from "@/shared/hooks/useDebounce";

import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import type { ObjectResult } from "@/entities/navigation/domain/search-anywhere";
import { useGetSearchAnywhere } from "@/entities/navigation/domain/search-anywhere.query";
import { searchCaseSensitiveAtom } from "@/entities/navigation/stores/search-case-sensitive.atom";
import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";
import { SearchAnywhereItem } from "@/entities/navigation/ui/search-anywhere/search-anywhere-item";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getSchemaObjectColumns } from "@/entities/nodes/object-items/getSchemaObjectColumns";
import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const SearchNodes = () => {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query.trim(), 300);
  const caseSensitive = useAtomValue(searchCaseSensitiveAtom);

  const { data, isPending, error } = useGetSearchAnywhere(
    { search: queryDebounced, caseSensitive },
    {
      enabled: !!queryDebounced,
    }
  );

  if (query === "") {
    return null;
  }

  if (isPending) {
    return (
      <SearchAnywhereGroup heading="Objects">
        <SearchAnywhereItem to="" disabled>
          Loading...
        </SearchAnywhereItem>
      </SearchAnywhereGroup>
    );
  }

  if (error) return null;

  if (data.count === 0) return null;

  return (
    <SearchAnywhereGroup heading="Objects">
      {data.matchingObjects.map((node) => (
        <NodesOptions key={node.id} node={node} />
      ))}
    </SearchAnywhereGroup>
  );
};

type NodesOptionsProps = {
  node: ObjectResult;
};

const NodesOptions = ({ node }: NodesOptionsProps) => {
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

  if (isPending) return <SearchResultNodeSkeleton />;

  if (error) return null;

  if (!objectDetailsData) return <div className="text-sm">No data found for this object</div>;

  const displayIpNamespace =
    isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema);

  const columns = getSchemaObjectColumns({
    schema,
    forListView: true,
    limit: displayIpNamespace ? 6 : 7,
    forSearchAnywhere: true,
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
          {displayIpNamespace && (
            <NodeAttribute
              title={"IP Namespace"}
              value={{ node: objectDetailsData?.ip_namespace?.node ?? undefined }}
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
    | { node: NodeCore }
    | { edges: Array<{ node: NodeCore }> };
};

const NodeAttribute = ({ title, kind, value }: NodeAttributeProps) => {
  const formatValue = (): string | number | boolean | ReactElement | null => {
    if ("node" in value && value.node) {
      return value.node ? getNodeLabel(value.node) : null;
    }

    if ("edges" in value && value.edges?.length > 0) {
      return value.edges.map(({ node }) => (node ? getNodeLabel(node) : "")).join(", ");
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
