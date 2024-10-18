import { Button } from "@/components/buttons/button-primitive";
import { Pill } from "@/components/display/pill";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { Table, tRowValue } from "@/components/table/table";
import { Pagination } from "@/components/ui/pagination";
import { ACCOUNT_GROUP_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { GET_ROLE_MANAGEMENT_GROUPS } from "@/graphql/queries/role-management/getGroups";
import useQuery from "@/hooks/useQuery";
import { useSchema } from "@/hooks/useSchema";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { useAtomValue } from "jotai";
import { useState } from "react";
import ErrorScreen from "../errors/error-screen";
import UnauthorizedScreen from "../errors/unauthorized-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { getPermission } from "../permission/utils";
import { GroupMembers } from "./group-member";

function Groups() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_GROUPS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(ACCOUNT_GROUP_OBJECT);
  const [rowToDelete, setRowToDelete] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [rowToUpdate, setRowToUpdate] = useState<Record<
    string,
    string | number | tRowValue
  > | null>(null);
  const [showDrawer, setShowDrawer] = useState(false);

  const permission = getPermission(data?.[ACCOUNT_GROUP_OBJECT]?.permissions?.edges);

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
      name: "members",
      label: "Members",
    },
    {
      name: "roles",
      label: "Roles",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_GROUP_OBJECT]?.edges.map((edge) => ({
      id: edge?.node?.id,
      values: {
        id: edge?.node?.id,
        name: { value: edge?.node?.name?.value },
        description: { value: edge?.node?.description?.value },
        group_type: { value: edge?.node?.group_type?.value },
        members: {
          value: { edges: edge?.node?.members?.edges },
          display: (
            <GroupMembers
              members={edge?.node?.members?.edges?.map((edge) => edge?.node?.display_label) ?? []}
            />
          ),
        },
        roles: {
          value: { edges: edge?.node?.roles?.edges },
          display: <Pill>{edge?.node?.roles?.count}</Pill>,
        },
        __typename: edge?.node?.__typename,
      },
    }));

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="An error occured while retrieving the accounts." />;
  }

  if (loading) {
    return <LoadingScreen message="Retrieving groups..." />;
  }

  if (!permission?.view.isAllowed) {
    return <UnauthorizedScreen message={permission?.view?.message} />;
  }

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
            <Button
              variant={"primary"}
              onClick={() => setShowDrawer(true)}
              disabled={!schema || !permission?.create.isAllowed}
            >
              Create {schema?.label}
            </Button>
          </div>
        </div>

        <Table
          columns={columns}
          rows={rows ?? []}
          className="border-0"
          onDelete={(data) => setRowToDelete(data.values)}
          onUpdate={(row) => {
            setRowToUpdate(row.values);
            setShowDrawer(true);
          }}
          permission={permission}
        />

        <Pagination count={data && data[ACCOUNT_GROUP_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[ACCOUNT_GROUP_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => setRowToDelete(null)}
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
          open={showDrawer}
          setOpen={(value) => setShowDrawer(value)}
        >
          <ObjectForm
            kind={ACCOUNT_GROUP_OBJECT}
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
  return <Groups />;
}
