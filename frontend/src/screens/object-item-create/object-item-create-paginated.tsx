import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import * as R from "ramda";
import { useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { getDropdownOptionsForRelatedPeersPaginated } from "../../graphql/queries/objects/dropdownOptionsForRelatedPeers";
import useQuery from "../../hooks/useQuery";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/getMutationDetailsFromFormData";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

interface iProps {
  objectname?: string;
  onCancel?: Function;
  onCreate: Function;
  refetch?: Function;
  formStructure?: DynamicFieldData[];
  customObject?: any;
  preventObjectsCreation?: boolean;
}

export default function ObjectItemCreate(props: iProps) {
  const {
    objectname,
    onCreate,
    onCancel,
    refetch,
    formStructure,
    customObject = {},
    preventObjectsCreation,
  } = props;

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericsList] = useAtom(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);

  const schema = schemaList.find((s) => s.kind === objectname);

  const peers = R.uniq((schema?.relationships || []).map((r) => r.peer).filter(Boolean));

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
    return <ErrorScreen message="Something went wrong when fetching dropdown options." />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (peers.length && !data) {
    return <NoDataFound message="No dropdown options found." />;
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
    try {
      const newObject = getMutationDetailsFromFormData(schema, data, "create");

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = createObject({
        kind: schema?.kind,
        data: stringifyWithoutQuotes({ ...newObject, ...customObject }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`${schema?.kind && schemaKindName[schema?.kind]} created`}
        />,
        { toastId: "alert-success" }
      );

      if (onCreate) {
        onCreate(result?.data?.[`${schema?.kind}Create`]);
      }

      if (refetch) refetch();

      setIsLoading(false);
    } catch (error: any) {
      console.error("An error occured while creating the object: ", error);

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
            preventObjectsCreation={preventObjectsCreation}
          />
        </div>
      )}
    </div>
  );
}
