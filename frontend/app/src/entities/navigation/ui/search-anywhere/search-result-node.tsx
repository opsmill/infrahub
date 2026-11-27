import type { ReactNode } from "react";

import { Icon } from "@/shared/components/display/icon";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { Badge } from "@/shared/components/ui/badge";
import { useFormatDate } from "@/shared/context/date-preferences-context";
import { classNames } from "@/shared/utils/common";

import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import type { ObjectResult } from "@/entities/navigation/domain/use-cases/search-anywhere";
import type {
  NodeAttributeWithMetadata,
  NodeObjectWithMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { getSchemaObjectColumns } from "@/entities/nodes/object/ui/object-table/get-schema-object-columns";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function useGetSearchResultObject(node: ObjectResult) {
  const { schema } = useSchema(node.kind);
  const {
    data: object,
    isPending,
    error,
  } = useGetObject(
    {
      objectSchema: schema!,
      objectId: node.id,
      getRelationshipsVisible: (relationships) =>
        relationships.filter((rel) => rel.cardinality === "one"),
    },
    { refetchOnWindowFocus: false } // Otherwise every loaded row refetches at once.
  );

  return { schema, object, isPending, error };
}

const MAX_ATTRIBUTE_COLUMNS = 7;

// Tracks of the same width put each attribute at the same position on every row, whatever its value.
const ATTRIBUTE_COLUMNS_STYLE = {
  gridTemplateColumns: `repeat(${MAX_ATTRIBUTE_COLUMNS}, minmax(0, 1fr))`,
};

interface SearchResultNodeSummaryProps {
  schema: ModelSchema;
  object: NodeObjectWithMetadata;
  attributeLayout?: "inline" | "columns";
}

export function SearchResultNodeSummary({
  schema,
  object,
  attributeLayout = "inline",
}: SearchResultNodeSummaryProps) {
  const displayIpNamespace =
    isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema);

  const columns = getSchemaObjectColumns({
    schema,
    forListView: true,
    limit: displayIpNamespace ? MAX_ATTRIBUTE_COLUMNS - 1 : MAX_ATTRIBUTE_COLUMNS,
    forSearchAnywhere: true,
  });

  return (
    <>
      <Icon
        icon={schema.icon || "mdi:code-braces-box"}
        className="px-2 py-0.5 text-accent text-lg"
      />

      <div className="grow overflow-auto text-sm">
        <div className="flex justify-between">
          <span className="mr-1 font-semibold text-accent">{getNodeLabel(object)}</span>

          <div className="inline-flex items-center gap-1">
            <Badge variant="blue" className="py-0 text-xxs">
              {schema.namespace}
            </Badge>
            <span className="mr-2 font-medium text-xxs">{schema.label}</span>
          </div>
        </div>

        <div
          className={classNames(
            "mt-1 gap-x-5 text-foreground-muted",
            attributeLayout === "columns" ? "grid" : "flex"
          )}
          style={attributeLayout === "columns" ? ATTRIBUTE_COLUMNS_STYLE : undefined}
        >
          {displayIpNamespace && (
            <NodeAttribute title={"IP Namespace"} value={object.ip_namespace} />
          )}

          {columns
            .filter(({ name }) => !["name", "label"].includes(name))
            .map((column) => (
              <NodeAttribute
                key={column.name}
                title={column.label ?? column.name}
                kind={"kind" in column ? column.kind : undefined}
                value={object[column.name]}
              />
            ))}
        </div>
      </div>
    </>
  );
}

export function SearchResultNodeSummarySkeleton() {
  return (
    <>
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
    </>
  );
}

type NodeAttributeProps = {
  title: string;
  kind?: string;
  value: NodeObjectWithMetadata[string];
};

interface DropdownAttribute extends NodeAttributeWithMetadata {
  label: string;
  color: string;
}

const isDropdownAttribute = (value: NodeAttributeWithMetadata): value is DropdownAttribute =>
  "label" in value &&
  typeof value.label === "string" &&
  "color" in value &&
  typeof value.color === "string";

const NodeAttribute = ({ title, kind, value }: NodeAttributeProps) => {
  const { formatDate } = useFormatDate();

  const formatValue = (): ReactNode => {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;

    if ("node" in value) {
      return value.node ? getNodeLabel(value.node) : null;
    }

    if ("edges" in value) {
      if (value.edges.length === 0) return null;
      return value.edges.map(({ node }) => (node ? getNodeLabel(node) : "")).join(", ");
    }

    if (!value.value) return null;

    switch (kind) {
      case ATTRIBUTE_KIND.BOOLEAN:
        return <Icon icon={value.value ? "mdi:check" : "mdi:remove"} className="text-sm" />;
      case ATTRIBUTE_KIND.COLOR:
        return (
          <div className="mt-0.5 h-4 w-4 rounded-sm" style={{ background: String(value.value) }} />
        );
      case ATTRIBUTE_KIND.DATETIME: {
        const date = typeof value.value === "string" ? new Date(value.value) : new Date();
        return formatDate(date, "datetime");
      }
      case ATTRIBUTE_KIND.DROPDOWN: {
        if (!isDropdownAttribute(value)) break;

        const color = value.color === "" ? "#f1f1f1" : value.color;
        return (
          <div
            className="truncate rounded-sm border border-transparent px-1.5 text-center font-medium text-foreground"
            style={{ background: `${color}40` }}
            title={value.label}
          >
            {value.label}
          </div>
        );
      }
    }

    return Array.isArray(value.value) ? value.value.join(", ") : value.value;
  };

  const formattedValue = formatValue();
  const valueText =
    typeof formattedValue === "string" || typeof formattedValue === "number"
      ? String(formattedValue)
      : undefined;

  return (
    <div className="flex flex-col overflow-hidden whitespace-nowrap text-xxs leading-3">
      <span title={title} className="truncate">
        {title}
      </span>
      <span
        title={valueText}
        className="max-w-full self-start truncate font-medium text-foreground"
      >
        {formattedValue || "-"}
      </span>
    </div>
  );
};
