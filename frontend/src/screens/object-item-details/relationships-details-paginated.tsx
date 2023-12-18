import { gql, useReactiveVar } from "@apollo/client";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { Pagination } from "../../components/pagination";
import { QSP } from "../../config/qsp";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { removeRelationship } from "../../graphql/mutations/relationships/removeRelationship";
import { getObjectRelationshipsDetailsPaginated } from "../../graphql/queries/objects/getObjectRelationshipDetails";
import { dateVar } from "../../graphql/variables/dateVar";
import usePagination from "../../hooks/usePagination";
import useQuery from "../../hooks/useQuery";
import { genericsState, iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { getAttributeColumnsFromNodeOrGenericSchema } from "../../utils/getSchemaObjectColumns";
import { stringifyWithoutQuotes } from "../../utils/string";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import RelationshipDetails from "./relationship-details-paginated";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "../../state/atoms/branches.atom";

interface RelationshipsDetailsProps {
  parentNode: any;
  parentSchema: iNodeSchema;
  refetchObjectDetails: Function;
}

export default function RelationshipsDetails(props: RelationshipsDetailsProps) {
  const { parentNode, parentSchema, refetchObjectDetails } = props;

  const { objectname, objectid } = useParams();
  const [relationshipTab] = useQueryParam(QSP.TAB, StringParam);
  const [pagination] = usePagination();
  const [schemaList] = useAtom(schemaState);
  const [generics] = useAtom(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useReactiveVar(dateVar);

  const schema = schemaList.find((s) => s.kind === objectname);
  const relationshipSchema = schema?.relationships?.find((r) => r?.name === relationshipTab);
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
    ...schema,
    relationship: relationshipTab,
    objectid,
    columns,
    filters: filtersString,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query, { skip: !relationshipTab });

  const updatePageData = () => {
    return Promise.all([refetch(), refetchObjectDetails()]);
  };

  if (loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the relationships." />;
  }

  if (!data || !relationshipTab) {
    return null;
  }

  const result = data[schema.kind]?.edges;

  const relationships = result?.length ? result[0]?.node[relationshipTab]?.edges : null;

  const handleDeleteRelationship = async (name: string, id: string) => {
    const mutationString = removeRelationship({
      data: stringifyWithoutQuotes({
        id: objectid,
        name,
        nodes: [
          {
            id,
          },
        ],
      }),
    });

    const mutation = gql`
      ${mutationString}
    `;

    await graphqlClient.mutate({
      mutation,
      context: { branch: branch?.name, date },
    });

    updatePageData();

    toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Item removed from the group"} />);
  };

  return (
    <div className="border-t border-gray-200 px-4 py-5 sm:p-0 flex flex-col flex-1 overflow-auto">
      <RelationshipDetails
        parentNode={parentNode}
        mode="TABLE"
        parentSchema={parentSchema}
        relationshipsData={relationships}
        relationshipSchema={relationshipSchema}
        refetch={updatePageData}
        onDeleteRelationship={handleDeleteRelationship}
      />

      <Pagination count={result[0]?.node[relationshipTab]?.count} />
    </div>
  );
}
