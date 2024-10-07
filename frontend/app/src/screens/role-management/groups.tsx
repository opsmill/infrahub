import { Button } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { Table } from "@/components/table/table";
import { Pagination } from "@/components/ui/pagination";
import { ACCOUNT_GROUP_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { GET_ROLE_MANAGEMENT_GROUPS } from "@/graphql/queries/role-management/getGroups";
import { useSchema } from "@/hooks/useSchema";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { useQuery } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useState } from "react";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { GroupMembers } from "./group-member";

function Groups() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_GROUPS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { schema } = useSchema(ACCOUNT_GROUP_OBJECT);
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
      name: "members",
      label: "Members",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_GROUP_OBJECT]?.edges.map((edge) => ({
      id: edge?.node?.id,
      values: {
        id: edge?.node?.id,
        display_label: edge?.node?.display_label,
        description: edge?.node?.description?.value,
        group_type: edge?.node?.group_type?.value,
        members: (
          <GroupMembers
            members={edge?.node?.members?.edges?.map((edge) => edge?.node?.display_label) ?? []}
          />
        ),
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
            <Button
              variant={"primary"}
              onClick={() => setShowCreateDrawer(true)}
              disabled={!schema}
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
          open={showCreateDrawer}
          setOpen={(value) => setShowCreateDrawer(value)}
        >
          <ObjectForm
            kind={ACCOUNT_GROUP_OBJECT}
            onCancel={() => setShowCreateDrawer(false)}
            onSuccess={() => {
              setShowCreateDrawer(false);
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
