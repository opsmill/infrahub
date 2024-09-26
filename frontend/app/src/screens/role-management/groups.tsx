import { useQuery } from "@apollo/client";
import { GET_ROLE_MANAGEMENT_GROUPS } from "@/graphql/queries/role-management/getGroups";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { ACCOUNT_GROUP_OBJECT, ACCOUNT_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import { GroupMembers } from "./group-member";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { useState } from "react";

function Groups() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_GROUPS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const [rowToDelete, setRowToDelete] = useState(null);

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
        display_label: edge?.node?.display_label,
        description: edge?.node?.description?.value,
        group_type: edge?.node?.group_type?.value,
        members: (
          <GroupMembers
            members={edge?.node?.members?.edges?.map((edge) => edge?.node?.display_label) ?? []}
          />
        ),
      },
    }));

  if (error) return <ErrorScreen message="An error occured while retrieving the accounts." />;

  if (loading) return <LoadingScreen message="Retrieving accounts..." />;

  return (
    <>
      <div>
        <Table
          columns={columns}
          rows={rows ?? []}
          className="border-0"
          onDelete={(data) => setRowToDelete(data.values)}
        />

        <Pagination count={data && data[ACCOUNT_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[ACCOUNT_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => setRowToDelete(null)}
        onDelete={refetch}
      />
    </>
  );
}

export function Component() {
  return <Groups />;
}
