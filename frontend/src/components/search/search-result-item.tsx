import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { Link } from "react-router-dom";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import useQuery from "../../hooks/useQuery";
import LoadingScreen from "../../screens/loading-screen/loading-screen";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import { getObjectAttributes, getObjectRelationships } from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "../../utils/objects";
import { Badge } from "../display/badge";

type tSearchResultItem = {
  item: any;
};

export const SearchResultItem = (props: tSearchResultItem) => {
  const { item } = props;

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericList] = useAtom(genericsState);

  const schema = schemaList.find((s) => s.kind === item.__typename);
  const generic = genericList.find((s) => s.kind === item.__typename);

  const schemaData = generic || schema;

  const attributes = getObjectAttributes(schemaData);
  const relationships = getObjectRelationships(schemaData);

  const queryString = schemaData
    ? getObjectDetailsPaginated({
        ...schemaData,
        attributes,
        relationships,
        objectid: item.id,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  // TODO: Find a way to avoid querying object details if we are on a tab
  const { loading, data } = useQuery(query, { skip: !schemaData });

  if (loading) return <LoadingScreen hideText size={20} />;

  const objectDetailsData = schemaData && data && data[item.__typename]?.edges[0]?.node;

  if (!objectDetailsData) return <div>No data found for this object</div>;

  return (
    <Link
      to={constructPath(getObjectDetailsUrl(objectDetailsData.id, objectDetailsData.__typename))}
      className="flex items-center px-2 mb-4 last:mb-0 text-sm rounded-md cursor-pointer hover:bg-gray-50">
      <Badge>{schemaKindName[item.__typename]}</Badge>

      {attributes.map((attribute: any, index: number) => (
        <div key={index} className="flex flex-col px-2 mr-4">
          <div className="text-xs italic">{attribute.label}</div>
          <div>{getObjectItemDisplayValue(objectDetailsData, attribute, schemaKindName)}</div>
        </div>
      ))}

      {relationships.map((relationship: any, index: number) => (
        <div key={index} className="flex flex-col px-2 mr-4">
          <div className="text-xs italic">{relationship.label}</div>
          <div>{getObjectItemDisplayValue(objectDetailsData, relationship, schemaKindName)}</div>
        </div>
      ))}
    </Link>
  );
};
