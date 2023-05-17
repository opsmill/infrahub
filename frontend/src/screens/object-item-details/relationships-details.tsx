import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { QSP } from "../../config/qsp";
import useQuery from "../../graphql/hooks/useQuery";
import { getObjectRelationshipsDetails } from "../../graphql/queries/objects/getObjectRelationshipDetails";
import { genericsState, iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { getAttributeColumnsFromNodeOrGenericSchema } from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import RelationshipDetails from "./relationship-details";

interface RelationshipsDetailsProps {
  parentNode: any;
  parentSchema: iNodeSchema;
}

export default function RelationshipsDetails(props: RelationshipsDetailsProps) {
  const { parentNode, parentSchema } = props;

  const { objectname, objectid } = useParams();
  const [relationshipTab] = useQueryParam(QSP.TAB, StringParam);
  const [schemaList] = useAtom(schemaState);
  const [generics] = useAtom(genericsState);

  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const relationshipSchema = schema?.relationships?.find((r) => r?.name === relationshipTab);
  const columns = getAttributeColumnsFromNodeOrGenericSchema(
    schemaList,
    generics,
    relationshipSchema?.peer!
  );

  const queryString = getObjectRelationshipsDetails({
    ...schema,
    relationship: relationshipTab,
    objectid,
    columns,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query, { skip: !relationshipTab });

  if (loading) {
    return <LoadingScreen />;
  }

  if (error) {
    console.error(`Error while loading the ${relationshipTab}:`, error);

    toast(
      <Alert type={ALERT_TYPES.ERROR} message={`Error while loading the ${relationshipTab}`} />
    );

    return <ErrorScreen />;
  }

  if (!data || !relationshipTab) {
    return null;
  }

  const result = data[schema.name];

  const relationships = result?.length ? result[0][relationshipTab] : null;

  return (
    <div className="border-t border-gray-200 px-4 py-5 sm:p-0 flex flex-col flex-1 overflow-auto">
      <RelationshipDetails
        parentNode={parentNode}
        mode="TABLE"
        parentSchema={parentSchema}
        relationshipsData={relationships}
        relationshipSchema={relationshipSchema}
        refetch={refetch}
      />
    </div>
  );
}
