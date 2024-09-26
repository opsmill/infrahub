import { useQuery } from "@apollo/client";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import {
  ACCOUNT_OBJECT,
  ACCOUNT_PERMISSION_OBJECT,
  GLOBAL_PERMISSION_OBJECT,
  OBJECT_PERMISSION_OBJECT,
} from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import { GET_ROLE_MANAGEMENT_PERMISSIONS } from "@/graphql/queries/role-management/getPermissions";
import { Pill } from "@/components/display/pill";
import { ReactNode, useState } from "react";
import { Icon } from "@iconify-icon/react";
import { BadgeCopy } from "@/components/ui/badge-copy";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";

const icons: Record<string, ReactNode> = {
  [GLOBAL_PERMISSION_OBJECT]: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-custom-blue-500/20">
      <Icon icon={"mdi:lock-outline"} className="text-red-900" />
    </Pill>
  ),
  [`${OBJECT_PERMISSION_OBJECT}_allow`]: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-green-500/40">
      <Icon icon={"mdi:lock-plus-outline"} className="text-green-900" />
    </Pill>
  ),
  [`${OBJECT_PERMISSION_OBJECT}_deny`]: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-red-500/40">
      <Icon icon={"mdi:lock-minus-outline"} className="text-red-900" />
    </Pill>
  ),
};

function Permissions() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_PERMISSIONS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const [rowToDelete, setRowToDelete] = useState(null);

  const columns = [
    {
      name: "display_label",
      label: "Name",
    },
    {
      name: "roles",
      label: "Roles",
    },
    {
      name: "identifier",
      label: "Identifier",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_PERMISSION_OBJECT]?.edges.map((edge) => {
      const iconKey = edge?.node?.decision?.value
        ? `${edge?.node?.__typename}_${edge?.node?.decision?.value}`
        : edge?.node?.__typename;

      const icon = icons[iconKey];

      return {
        id: edge?.node?.id,
        values: {
          display_label: (
            <div className="flex items-center gap-2">
              {icon} {edge?.node?.display_label}
            </div>
          ),
          description: edge?.node?.description?.value,
          roles: <Pill>{edge?.node?.roles?.count}</Pill>,
          identifier: <BadgeCopy value="test" />,
        },
      };
    });

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
  return <Permissions />;
}
