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
import { useSchema } from "@/hooks/useSchema";
import graphqlClient from "@/graphql/graphqlClientApollo";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import { Pill } from "@/components/display/pill";

function Accounts() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_ACCOUNTS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(ACCOUNT_GENERIC_OBJECT);

  const [rowToDelete, setRowToDelete] = useState(null);
  const [rowToUpdate, setRowToUpdate] = useState(null);
  const [showCreateDrawer, setShowDrawer] = useState(false);

  const columns = [
    {
      name: "name",
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
    {
      name: "member_of_groups",
      label: "Groups",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_GENERIC_OBJECT]?.edges.map((edge) => ({
      values: {
        id: edge?.node?.id,
        name: { value: edge?.node?.name?.value },
        description: { value: edge?.node?.description?.value },
        account_type: { value: edge?.node?.account_type?.value },
        status: {
          value: edge?.node?.status?.value,
          display: (
            <ColorDisplay
              color={edge?.node?.status?.color}
              value={edge?.node?.status?.value}
              description={edge?.node?.status?.description}
            />
          ),
        },
        member_of_groups: {
          value: { edges: edge?.node?.member_of_groups?.edges },
          display: <Pill>{edge?.node?.member_of_groups?.count}</Pill>,
        },
        __typename: edge?.node?.__typename,
      },
    }));

  if (error) return <ErrorScreen message="An error occured while retrieving the accounts." />;

  if (loading) return <LoadingScreen message="Retrieving accounts..." />;

  const globalRefetch = () => {
    graphqlClient.refetchQueries({ include: ["GET_ROLE_MANAGEMENT_COUNTS"] });
    refetch();
  };

  return (
    <>
      <div>
        <div className="flex items-center justify-between p-2">
          <div>{/* Search input + filter button */}</div>

          <div>
            <Button variant={"primary"} onClick={() => setShowDrawer(true)} disabled={!schema}>
              Create {schema?.label}
            </Button>
          </div>
        </div>

        <Table
          columns={columns}
          rows={rows ?? []}
          className="border-0"
          onDelete={(row) => setRowToDelete(row.values)}
          onUpdate={(row) => {
            setRowToUpdate(row.values);
            setShowDrawer(true);
          }}
        />

        <Pagination count={data && data[ACCOUNT_GENERIC_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[ACCOUNT_GENERIC_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => {
          setRowToDelete(null);
        }}
        onDelete={() => globalRefetch()}
      />

      {schema && (
        <SlideOver
          title={
            <SlideOverTitle
              schema={schema}
              currentObjectLabel="New"
              title={`Create ${schema.label}`}
              subtitle={schema.description}
            />
          }
          open={showCreateDrawer && !!rowToUpdate}
          setOpen={(value) => setShowDrawer(value)}>
          <ObjectForm
            kind={ACCOUNT_OBJECT}
            currentObject={rowToUpdate}
            onCancel={() => setShowDrawer(false)}
            onSuccess={() => {
              setShowDrawer(false);
              globalRefetch();
            }}
          />
        </SlideOver>
      )}
    </>
  );
}

export function Component() {
  return <Accounts />;
}
