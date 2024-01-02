import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useContext, useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { getObjectDetailsAndPeers } from "../../graphql/queries/objects/getObjectDetailsAndPeers";
import useQuery from "../../hooks/useQuery";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/getMutationDetailsFromFormData";
import {
  getSchemaAttributeColumns,
  getSchemaRelationshipColumns,
} from "../../utils/getSchemaObjectColumns";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

interface Props {
  objectname: string;
  objectid: string;
  closeDrawer: Function;
  onUpdateComplete: Function;
  formStructure?: DynamicFieldData[];
}

export default function ObjectItemEditComponent(props: Props) {
  const {
    objectname,
    objectid,
    closeDrawer,
    onUpdateComplete,
    formStructure: formStructureFromProps,
  } = props;

  const user = useContext(AuthContext);

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericsList] = useAtom(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);

  const schema = schemaList.find((s) => s.kind === objectname);

  const attributes = getSchemaAttributeColumns(schema, true);
  const relationships = getSchemaRelationshipColumns(schema);

  const peers = (schema?.relationships || []).map((r) => r.peer).filter(Boolean);

  const queryString = schema
    ? getObjectDetailsAndPeers({
        ...schema,
        attributes,
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
    return <ErrorScreen message="Something went wrong when fetching the object details." />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (!data || (data && !data[schema.kind])) {
    return <NoDataFound message="No details found." />;
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

  const formStructure =
    formStructureFromProps ??
    getFormStructureForCreateEdit(
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
          kind: schema?.kind,
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

        toast(
          <Alert type={ALERT_TYPES.SUCCESS} message={`${schemaKindName[schema.kind]} updated`} />
        );

        closeDrawer();

        onUpdateComplete();

        setIsLoading(false);
      } catch (e) {
        console.error("Something went wrong while updating the object:", e);
      }

      setIsLoading(false);
    }
  }

  return (
    <div className="bg-custom-white flex-1 overflow-auto flex flex-col" data-cy="object-item-edit">
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
