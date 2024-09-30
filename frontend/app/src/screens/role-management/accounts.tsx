import { gql } from "@apollo/client";
import { useQuery } from "@apollo/client";
import { GET_ROLE_MANAGEMENT_ACCOUNTS } from "@/graphql/queries/role-management/getAccounts";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { ACCOUNT_GENERIC_OBJECT, ACCOUNT_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { useState } from "react";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { ColorDisplay } from "@/components/display/color-display";
import { Button } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import DynamicForm from "@/components/form/dynamic-form";
import { isRequired } from "@/components/form/utils/validation";
import { useSchema } from "@/hooks/useSchema";
import { DropdownOption } from "@/components/inputs/dropdown";
import { getCreateMutationFromFormData } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { stringifyWithoutQuotes } from "@/utils/string";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";

function Accounts() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_ACCOUNTS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(ACCOUNT_GENERIC_OBJECT);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [rowToDelete, setRowToDelete] = useState(null);
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);

  const columns = [
    {
      name: "display_label",
      label: "Name",
    },
    {
      name: "description",
      label: "Description",
    },
    {
      name: "account_type",
      label: "Type",
    },
    {
      name: "status",
      label: "Status",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_GENERIC_OBJECT]?.edges.map((edge) => ({
      values: {
        id: edge?.node?.id,
        display_label: edge?.node?.display_label,
        description: edge?.node?.description?.value,
        account_type: edge?.node?.account_type?.value,
        status: (
          <ColorDisplay
            color={edge?.node?.status?.color}
            value={edge?.node?.status?.value}
            description={edge?.node?.status?.description}
          />
        ),
        __typename: edge?.node?.__typename,
      },
    }));

  if (error) return <ErrorScreen message="An error occured while retrieving the accounts." />;

  if (loading) return <LoadingScreen message="Retrieving accounts..." />;

  const enumOptions: DropdownOption[] =
    schema?.attributes
      ?.find((attribute) => attribute.name === "account_type")
      ?.enum?.map((data) => ({ value: data as string, label: data as string })) ?? [];

  const fields: DynamicFieldProps[] = [
    {
      name: "name",
      label: "Name",
      type: "Text",
      rules: { required: true, validate: { required: isRequired } },
    },
    {
      name: "password",
      label: "Password",
      type: "Password",
      rules: { required: true, validate: { required: isRequired } },
    },
    {
      name: "description",
      label: "Description",
      type: "Text",
    },
    {
      name: "label",
      label: "Label",
      type: "Text",
    },
    {
      name: "account_type",
      label: "Type",
      type: "Dropdown",
      items: enumOptions,
    },
  ];

  async function refetchCount() {
    await graphqlClient.refetchQueries({ include: ["GET_ROLE_MANAGEMENT_COUNTS"] });
  }

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormData(fields, data);
      const isObjectEmpty = Object.keys(newObject).length === 0;

      if (isObjectEmpty) {
        return;
      }

      const mutationString = createObject({
        kind: ACCOUNT_OBJECT,
        data: stringifyWithoutQuotes(newObject),
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

      await refetch();
      await refetchCount();
      setShowCreateDrawer(false);

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Account created"} />, {
        toastId: "alert-success-account-created",
      });
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <>
      <div>
        <div className="flex items-center justify-between p-2">
          <div>SEARCH + FILTERS</div>

          <div>
            <Button
              variant={"primary"}
              onClick={() => setShowCreateDrawer(true)}
              disabled={!schema}>
              Create Account
            </Button>
          </div>
        </div>

        <Table
          columns={columns}
          rows={rows ?? []}
          className="border-0"
          onDelete={(data) => setRowToDelete(data.values)}
        />

        <Pagination count={data && data[ACCOUNT_GENERIC_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[ACCOUNT_GENERIC_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => {
          setRowToDelete(null);
          refetchCount();
        }}
        onDelete={refetch}
      />

      {schema && (
        <SlideOver
          title={
            <SlideOverTitle
              schema={schema}
              currentObjectLabel="New"
              title={"Create Account"}
              subtitle={schema?.description}
            />
          }
          open={showCreateDrawer}
          setOpen={setShowCreateDrawer}>
          <DynamicForm
            fields={fields}
            onSubmit={handleSubmit}
            onCancel={() => setShowCreateDrawer(false)}
            className="p-4"
          />
        </SlideOver>
      )}
    </>
  );
}

export function Component() {
  return <Accounts />;
}
