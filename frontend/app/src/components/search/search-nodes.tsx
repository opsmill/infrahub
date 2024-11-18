import { Skeleton } from "@/components/skeleton";
import { Badge } from "@/components/ui/badge";
import { SCHEMA_ATTRIBUTE_KIND, SEARCH_QUERY_NAME } from "@/config/constants";
import { SEARCH } from "@/graphql/queries/objects/search";
import { useDebounce } from "@/hooks/useDebounce";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import { useLazyQuery } from "@/hooks/useQuery";
import { useSchema } from "@/hooks/useSchema";
import { constructPath } from "@/utils/fetch";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "@/utils/objects";
import { Icon } from "@iconify-icon/react";
import { format } from "date-fns";
import { ReactElement, useEffect } from "react";
import { SearchGroup, SearchGroupTitle, SearchResultItem } from "./search-anywhere";

type SearchProps = {
  query: string;
};
export const SearchNodes = ({ query }: SearchProps) => {
  const queryDebounced = useDebounce(query, 300);
  const [fetchSearchNodes, { data, previousData, error }] = useLazyQuery(SEARCH);

  useEffect(() => {
    const cleanedValue = queryDebounced.trim();
    fetchSearchNodes({ variables: { search: cleanedValue } });
  }, [queryDebounced]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center">
        <Icon icon="mdi:error" className="text-2xl px-2 py-0.5" />
        <p className="text-sm">{error.message}</p>
      </div>
    );
  }

  const results = (data || previousData)?.[SEARCH_QUERY_NAME];

  if (!results || results?.count === 0) return null;

  return (
    <SearchGroup>
      <SearchGroupTitle>Search results for &quot;{query}&quot;</SearchGroupTitle>

      {results.edges.map(({ node }: NodesOptionsProps) => (
        <NodesOptions key={node.id} node={node} />
      ))}
    </SearchGroup>
  );
};

type NodesOptionsProps = {
  node: {
    id: string;
    kind: string;
  };
};

const NodesOptions = ({ node }: NodesOptionsProps) => {
  const { schema } = useSchema(node.kind);
  const { data, loading, error } = useObjectDetails(schema!, node.id);

  if (!schema) return null;
  const columns = getSchemaObjectColumns({ schema, forListView: true, limit: 7 });

  if (loading) return <SearchResultNodeSkeleton />;

  if (error) {
    return (
      <div className="text-sm text-red-600">
        Error loading object details for {node.kind} (id: {node.id})
      </div>
    );
  }

  const objectDetailsData = schema && data?.[node.kind]?.edges[0]?.node;
  if (!objectDetailsData) return <div className="text-sm">No data found for this object</div>;

  const url = constructPath(
    getObjectDetailsUrl(objectDetailsData.id, objectDetailsData.__typename)
  );

  return (
    <SearchResultItem to={url} className="!items-start">
      <Icon
        icon={schema.icon || "mdi:code-braces-box"}
        className="text-lg pr-2 py-0.5 text-custom-blue-700"
      />

      <div className="flex-grow text-sm">
        <div className="flex justify-between">
          <span className="mr-1 font-semibold text-custom-blue-800">
            {objectDetailsData?.display_label}
          </span>

          <div className="inline-flex items-center gap-1">
            <Badge variant="blue" className="text-xxs py-0">
              {schema.namespace}
            </Badge>
            <span className="text-xxs font-medium">{schema.label}</span>
          </div>
        </div>

        <div className="mt-1 text-gray-600 flex gap-5">
          {columns
            .filter(({ name }) => !["name", "label"].includes(name))
            .map((column) => (
              <NodeAttribute
                key={column.id}
                title={column.label}
                kind={column.kind}
                value={objectDetailsData[column.name]}
              />
            ))}
        </div>
      </div>
    </SearchResultItem>
  );
};

type NodeAttributeProps = {
  title: string;
  kind: string;
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
        case SCHEMA_ATTRIBUTE_KIND.BOOLEAN:
          return <Icon icon={value.value ? "mdi:check" : "mdi:remove"} className="text-sm" />;
        case SCHEMA_ATTRIBUTE_KIND.COLOR:
          return (
            <div className="h-4 w-4 rounded mt-0.5" style={{ background: value.value as string }} />
          );
        case SCHEMA_ATTRIBUTE_KIND.DATETIME:
          const date = typeof value.value === "string" ? new Date(value.value) : new Date();
          return format(date, "yyyy/MM/dd HH:mm");
        case SCHEMA_ATTRIBUTE_KIND.DROPDOWN:
          if (!("color" in value)) return value.value;

          const color = value.color === "" ? "#f1f1f1" : value.color;
          return (
            <div
              className="px-1.5 rounded text-gray-700 font-medium text-center border border-transparent"
              style={{ background: `${color}40` }}
            >
              {value.label}
            </div>
          );
      }
      return value.value;
    }

    return null;
  };

  return (
    <div className="flex flex-col text-xxs whitespace-nowrap leading-3">
      <span>{title}</span>
      <span className="font-medium text-gray-800">{formatValue() || "-"}</span>
    </div>
  );
};

export const SearchResultNodeSkeleton = () => {
  return (
    <div className="flex py-2 w-full">
      <Skeleton className="h-6 w-6 rounded mx-1 mr-2" />

      <div className="space-y-2 flex-grow">
        <div className="flex space-x-2">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-3 w-20" />
        </div>
        <div className="space-y-1">
          <Skeleton className="h-3 max-w-xl" />
          <Skeleton className="h-3 max-w-xl" />
        </div>
      </div>
    </div>
  );
};
