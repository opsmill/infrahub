import { useQuery } from "@apollo/client";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { ACCOUNT_ROLE_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import { GET_ROLE_MANAGEMENT_ROLES } from "@/graphql/queries/role-management/getRoles";
import { Pill } from "@/components/display/pill";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { useState } from "react";

function Roles() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_ROLES);
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
      name: "groups",
      label: "Groups",
    },
    {
      name: "permissions",
      label: "Permissions",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_ROLE_OBJECT]?.edges.map((edge) => ({
      id: edge?.node?.id,
      values: {
        display_label: edge?.node?.display_label,
        description: edge?.node?.description?.value,
        groups: <Pill>{edge?.node?.groups?.count}</Pill>,
        permissions: <Pill>{edge?.node?.permissions?.count}</Pill>,
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

        <Pagination count={data && data[ACCOUNT_ROLE_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[ACCOUNT_ROLE_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => setRowToDelete(null)}
        onDelete={refetch}
      />
    </>
  );
}

export function Component() {
  return <Roles />;
}
