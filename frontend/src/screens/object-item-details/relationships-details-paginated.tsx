import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Pagination } from "@/components/ui/pagination";
import { QSP } from "@/config/qsp";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { removeRelationship } from "@/graphql/mutations/relationships/removeRelationship";
import { getObjectRelationshipsDetailsPaginated } from "@/graphql/queries/objects/getObjectRelationshipDetails";
import useQuery from "@/hooks/useQuery";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { genericsState, iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { forwardRef, useEffect, useImperativeHandle } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import RelationshipDetails from "./relationship-details-paginated";

interface RelationshipsDetailsProps {
  parentNode: any;
  parentSchema: iNodeSchema;
  refetchObjectDetails: Function;
}

// Forward ref needed to provide ref to parent to refetch
export const RelationshipsDetails = forwardRef((props: RelationshipsDetailsProps, ref) => {
  const { parentNode, refetchObjectDetails } = props;

  const { objectname, objectid } = useParams();
  const [relationshipTab] = useQueryParam(QSP.TAB, StringParam);
  const [schemaList] = useAtom(schemaState);
  const [generics] = useAtom(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const parentSchema = schemaList.find((s) => s.kind === objectname);
  const parentGeneric = generics.find((s) => s.kind === objectname);
  const relationshipSchema = parentSchema?.relationships?.find((r) => r?.name === relationshipTab);
  const relationshipGeneric = parentGeneric?.relationships?.find(
    (r) => r?.name === relationshipTab
  );
  const relationshipSchemaData = relationshipSchema || relationshipGeneric;
  const schema = schemaList.find((s) => s.kind === relationshipSchemaData?.peer);
  const generic = generics.find((s) => s.kind === relationshipSchemaData?.peer);
  const schemaData = schema || generic;

  const columns = getSchemaObjectColumns({ schema: schemaData, forListView: true });

  const queryString = schemaData
    ? getObjectRelationshipsDetailsPaginated({
        kind: objectname,
        relationshipKind: !!columns?.length && relationshipSchemaData?.peer,
        objectid: parentNode.id,
        relationship: relationshipTab,
        columns,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  useEffect(() => {
    // Refetch on mount to update tab counter if needed
    // TODO: improve test before refetching data
    refetchObjectDetails();
  }, []);

  const { loading, error, data, refetch } = useQuery(query, { skip: !relationshipTab });

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

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

  // const count = data[schemaData?.kind].count;
  const count = data[objectname]?.edges[0]?.node[relationshipTab]?.count;
  // const relationshipsData = data[schemaData?.kind]?.edges;
  const relationshipsData = data[objectname]?.edges[0]?.node[relationshipTab]?.edges;

  return (
    <div>
      <RelationshipDetails
        parentNode={parentNode}
        mode="TABLE"
        relationshipsData={relationshipsData}
        relationshipSchema={relationshipSchema}
        relationshipSchemaData={schemaData}
        refetch={updatePageData}
        onDeleteRelationship={handleDeleteRelationship}
      />

      <Pagination count={count} />
    </div>
  );
});
