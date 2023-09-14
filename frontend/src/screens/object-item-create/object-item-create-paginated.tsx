import { gql, useReactiveVar } from "@apollo/client";
import { useAtom } from "jotai";
import { useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { getDropdownOptionsForRelatedPeersPaginated } from "../../graphql/queries/objects/dropdownOptionsForRelatedPeers";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import useQuery from "../../hooks/useQuery";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/getMutationDetailsFromFormData";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

interface iProps {
  objectname: string;
  onCancel?: Function;
  onCreate: Function;
  refetch?: Function;
  formStructure: DynamicFieldData[];
  customObject?: any;
}

export default function ObjectItemCreate(props: iProps) {
  console.log("RENDER CREATE");
  const { objectname, onCreate, onCancel, refetch, formStructure, customObject = {} } = props;

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericsList] = useAtom(genericsState);
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [isLoading, setIsLoading] = useState(false);

  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const peers = (schema.relationships || []).map((r) => r.peer).filter(Boolean);

  const queryString = peers.length
    ? getDropdownOptionsForRelatedPeersPaginated({
        peers,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for default query
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { skip: !schema || !peers.length });

  if (error) {
    return <ErrorScreen />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (peers.length && !data) {
    return <NoDataFound />;
  }

  const objectDetailsData = data && data[schema.kind];

  const peerDropdownOptions =
    data &&
    Object.entries(data).reduce((acc, [k, v]: [string, any]) => {
      if (peers.includes(k)) {
        return { ...acc, [k]: v?.edges?.map((edge: any) => edge?.node) };
      }

      return acc;
    }, {});

  const fields =
    formStructure ??
    getFormStructureForCreateEdit(
      schema,
      schemaList,
      genericsList,
      peerDropdownOptions,
      objectDetailsData
    );

  async function onSubmit(data: any) {
    setIsLoading(true);

    const newObject = getMutationDetailsFromFormData(schema, data, "create");

    if (!Object.keys(newObject).length) {
      return;
    }

    try {
      const mutationString = createObject({
        kind: schema.kind,
        data: stringifyWithoutQuotes({ ...newObject, ...customObject }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      toast(
        <Alert type={ALERT_TYPES.SUCCESS} message={`${schemaKindName[schema.kind]} created`} />
      );

      if (onCreate) {
        onCreate();
      }

      console.log("DONE");

      setTimeout(() => {
        console.log("REFETCH");
        if (refetch) refetch();
      }, 3000);

      setIsLoading(false);
    } catch (error: any) {
      console.error("An error occured while creating the object: ", error);

      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"An error occured while creating the object"}
          details={error.message}
        />
      );
      setIsLoading(false);
    }
  }

  return (
    <div className="bg-custom-white flex-1 overflow-auto flex">
      {schema && fields && (
        <div className="flex-1">
          <EditFormHookComponent
            onSubmit={onSubmit}
            onCancel={onCancel}
            fields={fields}
            isLoading={isLoading}
            submitLabel={"Create"}
          />
        </div>
      )}
    </div>
  );
}
