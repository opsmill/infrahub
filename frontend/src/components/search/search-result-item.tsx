import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { Link as RouterLink } from "react-router-dom";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import useQuery from "../../hooks/useQuery";
import LoadingScreen from "../../screens/loading-screen/loading-screen";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import { getSchemaObjectColumns } from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "../../utils/objects";
import { Badge } from "../display/badge";
import { Link } from "../utils/link";

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

  const columns = getSchemaObjectColumns(schemaData, 10);

  const queryString = schemaData
    ? getObjectDetailsPaginated({
        ...schemaData,
        columns,
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

  const allObjectsPath = `/objects/${item.__typename}`;

  if (!objectDetailsData) return <div>No data found for this object</div>;

  return (
    <div className="flex flex-col flex-1 items-start mb-4 last:mb-0 ">
      <RouterLink
        to={constructPath(getObjectDetailsUrl(objectDetailsData.id, objectDetailsData.__typename))}
        className="flex-1 p-2 text-sm rounded-md cursor-pointer hover:bg-gray-50">
        <div className="flex flex-1 flex-col">
          <div className="flex items-center mb-4">
            <Badge>{schemaKindName[item.__typename]}</Badge>

            <div className="font-semibold">{objectDetailsData?.name?.value}</div>
          </div>

          <div className="flex divide-x">
            {columns.map((column: any, index: number) => (
              <div key={index} className="flex flex-col px-2 mr-4">
                <div className="text-xs italic text-gray-600">{column.label}</div>
                {getObjectItemDisplayValue(objectDetailsData, column, schemaKindName)}
              </div>
            ))}
          </div>
        </div>
      </RouterLink>

      <Link
        to={constructPath(allObjectsPath)}
        target="_blank"
        className="p-2 flex items-center text-xs">
        {schemaKindName[item.__typename]} (All)
        <Icon icon="mdi:open-in-new" className="ml-2" />
      </Link>
    </div>
  );
};
