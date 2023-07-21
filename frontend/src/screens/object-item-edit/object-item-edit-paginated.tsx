import { gql, useReactiveVar } from "@apollo/client";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { getObjectDetailsAndPeers } from "../../graphql/queries/objects/getObjectDetailsAndPeers";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import useQuery from "../../hooks/useQuery";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/getMutationDetailsFromFormData";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import { stringifyWithoutQuotes } from "../../utils/string";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

interface Props {
  objectname: string;
  objectid: string;
  closeDrawer: Function;
  onUpdateComplete: Function;
}

export default function ObjectItemEditComponent(props: Props) {
  const { objectname, objectid, closeDrawer, onUpdateComplete } = props;

  const user = useContext(AuthContext);

  const [schemaList] = useAtom(schemaState);
  const [genericsList] = useAtom(genericsState);
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [isLoading, setIsLoading] = useState(false);

  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const relationships = getSchemaRelationshipColumns(schema);

  const peers = (schema.relationships || []).map((r) => r.peer).filter(Boolean);

  const queryString = schema
    ? getObjectDetailsAndPeers({
        ...schema,
        relationships,
        objectid,
        peers,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { skip: !schema });

  if (error) {
    console.error("An error occured while retrieving the object details: ", error);

    toast(
      <Alert
        message="An error occured while retrieving the object details"
        type={ALERT_TYPES.ERROR}
      />
    );

    return <ErrorScreen />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (!data || (data && !data[schema.kind])) {
    return <NoDataFound />;
  }

  const objectDetailsData = data[schema.kind]?.edges[0]?.node;

  const peerDropdownOptions = Object.entries(data).reduce((acc, [k, v]: [string, any]) => {
    if (peers.includes(k)) {
      return {
        ...acc,
        [k]: v.edges?.map((edge: any) => edge.node),
      };
    }
    return acc;
  }, {});

  const formStructure = getFormStructureForCreateEdit(
    schema,
    schemaList,
    genericsList,
    peerDropdownOptions,
    objectDetailsData,
    user
  );

  async function onSubmit(data: any) {
    setIsLoading(true);

    const updatedObject = getMutationDetailsFromFormData(schema, data, "update", objectDetailsData);

    if (Object.keys(updatedObject).length) {
      try {
        const mutationString = updateObjectWithId({
          kind: schema.kind,
          data: stringifyWithoutQuotes({
            id: objectid,
            ...updatedObject,
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: branch?.name, date },
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema.name} updated`} />);

        closeDrawer();

        onUpdateComplete();
        setIsLoading(false);

        return;
      } catch (e) {
        setIsLoading(false);
        toast(
          <Alert
            message="Something went wrong while updating the object"
            type={ALERT_TYPES.ERROR}
          />
        );
        console.error("Something went wrong while updating the object:", e);
        return;
      }
    }
  }

  return (
    <div className="bg-custom-white flex-1 overflow-auto flex flex-col">
      {formStructure && (
        <EditFormHookComponent
          onCancel={props.closeDrawer}
          onSubmit={onSubmit}
          fields={formStructure}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}
