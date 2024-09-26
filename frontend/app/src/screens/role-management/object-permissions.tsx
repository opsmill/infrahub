import { useQuery } from "@apollo/client";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { OBJECT_PERMISSION_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import { Pill } from "@/components/display/pill";
import { ReactNode, useState } from "react";
import { Icon } from "@iconify-icon/react";
import { BadgeCopy } from "@/components/ui/badge-copy";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS } from "@/graphql/queries/role-management/getObjectPermissions";

const icons: Record<string, ReactNode> = {
  allow: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-green-500/40">
      <Icon icon={"mdi:lock-plus-outline"} className="text-green-900" />
    </Pill>
  ),
  deny: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-red-500/40">
      <Icon icon={"mdi:lock-minus-outline"} className="text-red-900" />
    </Pill>
  ),
};

function Permissions() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const [rowToDelete, setRowToDelete] = useState(null);

  const columns = [
    {
      name: "name",
      label: "Name",
    },
    {
      name: "branch",
      label: "Branch",
    },
    {
      name: "namespace",
      label: "Namespace",
    },
    {
      name: "action",
      label: "Action",
    },
    {
      name: "decision",
      label: "Decision",
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
    data[OBJECT_PERMISSION_OBJECT]?.edges.map((edge) => {
      const iconKey = edge?.node?.decision?.value;
      const icon = icons[iconKey];

      return {
        id: edge?.node?.id,
        values: {
          display_label: edge?.node?.display_label,
          name: (
            <div className="flex items-center gap-2">
              {icon} {edge?.node?.display_label}
            </div>
          ),
          branch: edge?.node?.branch?.value,
          namespace: edge?.node?.namespace?.value,
          action: edge?.node?.action?.value,
          decision: edge?.node?.decision?.value,
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

        <Pagination count={data && data[OBJECT_PERMISSION_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[OBJECT_PERMISSION_OBJECT]}
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
