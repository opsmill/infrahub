import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { getDropdownOptionsForRelatedPeersPaginated } from "../../graphql/queries/objects/dropdownOptionsForRelatedPeers";
import useQuery from "../../hooks/useQuery";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/mutationDetailsFromFormData";
import { stringifyWithoutQuotes } from "../../utils/string";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

interface iProps {
  objectname: string;
  onCancel?: Function;
  onCreate: Function;
}

export default function ObjectItemCreate(props: iProps) {
  const { objectname, onCreate, onCancel } = props;

  const [schemaList] = useAtom(schemaState);
  const [schemaKindNameMap] = useAtom(schemaKindNameState);
  const [genericsList] = useAtom(genericsState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const peers = (schema.relationships || []).map((r) => schemaKindNameMap[r.peer]).filter(Boolean);

  const queryString = peers.length
    ? getDropdownOptionsForRelatedPeersPaginated({
        peers,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query, { skip: !schema || !peers.length });

  if (error) {
    return <ErrorScreen />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (peers.length && !data) {
    return <NoDataFound />;
  }

  const objectDetailsData = data && data[schema.name];

  const peerDropdownOptions =
    data &&
    Object.entries(data).reduce((acc, [k, v]: [string, any]) => {
      if (peers.includes(k)) {
        return { ...acc, [k]: v?.edges?.map((edge: any) => edge?.node) };
      }

      return acc;
    }, {});

  const formStructure = getFormStructureForCreateEdit(
    schema,
    schemaList,
    genericsList,
    peerDropdownOptions,
    schemaKindNameMap,
    objectDetailsData
  );

  async function onSubmit(data: any) {
    const newObject = getMutationDetailsFromFormData(schema, data, "create");

    if (!Object.keys(newObject).length) {
      return;
    }

    try {
      const mutationString = createObject({
        name: schema.name,
        data: stringifyWithoutQuotes(newObject),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema.kind} created`} />);

      if (onCreate) {
        onCreate();
      }

      refetch();
    } catch (error: any) {
      console.error("An error occured while creating the object: ", error);

      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"An error occured while creating the object"}
          details={error.message}
        />
      );
    }
  }

  return (
    <div className="bg-white flex-1 overflow-auto flex">
      {schema && formStructure && (
        <div className="flex-1">
          <EditFormHookComponent
            onSubmit={onSubmit}
            onCancel={() => (onCancel ? onCancel() : null)}
            fields={formStructure}
          />
        </div>
      )}
    </div>
  );
}
