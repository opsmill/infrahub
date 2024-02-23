import useQuery, { useLazyQuery } from "../../hooks/useQuery";
import { SEARCH } from "../../graphql/queries/objects/search";
import { ReactElement, useEffect } from "react";
import LoadingScreen from "../../screens/loading-screen/loading-screen";
import { Icon } from "@iconify-icon/react";
import { NODE_OBJECT, SCHEMA_ATTRIBUTE_KIND } from "../../config/constants";
import { useAtomValue } from "jotai/index";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { getSchemaObjectColumns } from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import { gql } from "@apollo/client";
import { constructPath } from "../../utils/fetch";
import { getObjectDetailsUrl } from "../../utils/objects";
import { Combobox } from "@headlessui/react";
import { Link } from "react-router-dom";
import { format } from "date-fns";

type SearchProps = {
  query: string;
};
export const SearchNodes = ({ query }: SearchProps) => {
  const [fetchSearchNodes, { data, error, loading }] = useLazyQuery(SEARCH);

  useEffect(() => {
    const cleanedValue = query.trim();
    fetchSearchNodes({ variables: { search: cleanedValue } });
  }, [query]);

  if (loading) {
    return (
      <div className="h-52 flex items-center justify-center">
        <LoadingScreen hideText />
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-52 flex flex-col items-center justify-center">
        <Icon icon="mdi:error" className="text-2xl px-2 py-0.5" />
        <p className="text-sm">{error.message}</p>
      </div>
    );
  }

  const results = data?.[NODE_OBJECT];

  if (!results || results?.count === 0) {
    return (
      <div className="h-52 flex flex-col items-center justify-center">
        <h2 className="text-sm font-semibold">No results found</h2>
        <p className="text-xs">Try using different keywords</p>
      </div>
    );
  }

  return results.edges.map(({ node }: NodesOptionsProps) => (
    <NodesOptions key={node.id} node={node} />
  ));
};

type NodesOptionsProps = {
  node: {
    id: string;
    __typename: string;
  };
};

const NodesOptions = ({ node }: NodesOptionsProps) => {
  const schemaList = useAtomValue(schemaState);
  const genericList = useAtomValue(genericsState);

  const schema = schemaList.find((s) => s.kind === node.__typename);
  const generic = genericList.find((s) => s.kind === node.__typename);

  const schemaData = generic || schema;

  // const columns = getSchemaObjectColumns(schemaData, true, 7);
  const columns = getSchemaObjectColumns(schemaData, true);

  const queryString = schemaData
    ? getObjectDetailsPaginated({
        ...schemaData,
        columns,
        objectid: node.id,
      })
    : // Empty query to make the gql parsing work
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, data } = useQuery(query, { skip: !schemaData });

  if (loading) return <LoadingScreen hideText size={20} />;

  const objectDetailsData = schemaData && data?.[node.__typename]?.edges[0]?.node;

  if (!objectDetailsData) return <div>No data found for this object</div>;

  const url = constructPath(
    getObjectDetailsUrl(objectDetailsData.id, objectDetailsData.__typename)
  );

  return (
    <Combobox.Option
      as={Link}
      value={url}
      to={url}
      className={({ active }) =>
        `flex gap-1 text-sm border-b border-gray-200 py-3 ${active ? "bg-slate-200" : ""}`
      }>
      <Icon
        icon={schemaData?.icon || "mdi:code-braces-box"}
        className="text-lg px-2 py-0.5 text-custom-blue-700"
      />

      <div className="flex-grow">
        <span className="mr-1 font-semibold text-custom-blue-700">
          {objectDetailsData?.display_label}
        </span>
        <span className="bg-gray-100 text-gray-800 text-xs me-1 px-2 py-0.5 rounded-full">
          {schemaData?.label}
        </span>

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
    </Combobox.Option>
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

          const color = value.color !== "" ? "#f1f1f1" : value.color;
          return (
            <div
              className="px-1.5 rounded-full text-gray-700 font-medium text-center"
              style={{ background: `${color}40`, border: `1px solid ${color}` }}>
              {value.label}
            </div>
          );
      }
      return value.value;
    }

    return null;
  };

  return (
    <div className="flex flex-col text-xxs whitespace-nowrap">
      <span className="font-light">{title}</span>
      <span className="font-medium">{formatValue() || "-"}</span>
    </div>
  );
};
