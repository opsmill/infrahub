import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Pagination } from "../../components/utils/pagination";
import { QSP } from "../../config/qsp";
import { getObjectRelationshipsDetailsPaginated } from "../../graphql/queries/objects/getObjectRelationshipDetails";
import usePagination from "../../hooks/usePagination";
import useQuery from "../../hooks/useQuery";
import { genericsState, iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { getAttributeColumnsFromNodeOrGenericSchema } from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import GroupRelationship from "./group-relationship";

interface RelationshipsDetailsProps {
  parentNode: any;
  parentSchema: iNodeSchema;
}

export default function GroupRelationships(props: RelationshipsDetailsProps) {
  const { parentNode, parentSchema } = props;

  const { groupname, groupid } = useParams();
  const [relationshipTab] = useQueryParam(QSP.TAB, StringParam);
  const [pagination] = usePagination();
  const [schemaList] = useAtom(schemaState);
  const [genericList] = useAtom(genericsState);
  const [generics] = useAtom(genericsState);

  const schema = schemaList.filter((s) => s.kind === groupname)[0];
  const generic = genericList.filter((s) => s.kind === groupname)[0];

  const relationshipSchema = schema?.relationships?.find((r) => r?.name === relationshipTab);

  const schemaData = generic || schema;

  const columns = getAttributeColumnsFromNodeOrGenericSchema(
    schemaList,
    generics,
    relationshipSchema?.peer!
  );

  const filtersString = [
    { name: "offset", value: pagination?.offset },
    { name: "limit", value: pagination?.limit },
  ]
    .map((row: any) => `${row.name}: ${row.value}`)
    .join(",");

  const queryString = getObjectRelationshipsDetailsPaginated({
    ...schemaData,
    relationship: relationshipTab,
    objectid: groupid,
    columns,
    filters: filtersString,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query, { skip: !relationshipTab });

  if (loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the group relationships." />;
  }

  if (!data || !relationshipTab) {
    return null;
  }

  const result = data[schema.kind]?.edges;

  const relationships = result?.length ? result[0]?.node[relationshipTab]?.edges : null;

  return (
    <div className="border-t border-gray-200 px-4 py-5 sm:p-0 flex flex-col flex-1 overflow-auto">
      <GroupRelationship
        parentNode={parentNode}
        parentSchema={parentSchema}
        relationshipsData={relationships}
        relationshipSchema={relationshipSchema}
        refetch={refetch}
      />

      <Pagination count={result[0]?.node[relationshipTab]?.count} />
    </div>
  );
}
