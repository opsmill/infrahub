import { useQuery } from "@apollo/client";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { GLOBAL_PERMISSION_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import { Pill } from "@/components/display/pill";
import { useState } from "react";
import { Icon } from "@iconify-icon/react";
import { BadgeCopy } from "@/components/ui/badge-copy";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS } from "@/graphql/queries/role-management/getGlobalPermissions";

function GlobalPermissions() {
  const { loading, data, error, refetch } = useQuery(GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS);
  const schemaKindName = useAtomValue(schemaKindNameState);
  const [rowToDelete, setRowToDelete] = useState(null);

  const columns = [
    {
      name: "name",
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
    data[GLOBAL_PERMISSION_OBJECT]?.edges.map((edge) => {
      return {
        id: edge?.node?.id,
        values: {
          display_label: edge?.node?.display_label,
          name: (
            <div className="flex items-center gap-2">
              <Pill className="flex items-center justify-center w-6 h-6 bg-custom-blue-500/20">
                <Icon icon={"mdi:lock-outline"} className="text-red-900" />
              </Pill>

              {edge?.node?.display_label}
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

        <Pagination count={data && data[GLOBAL_PERMISSION_OBJECT]?.count} />
      </div>

      <ModalDeleteObject
        label={schemaKindName[GLOBAL_PERMISSION_OBJECT]}
        rowToDelete={rowToDelete}
        open={!!rowToDelete}
        close={() => setRowToDelete(null)}
        onDelete={refetch}
      />
    </>
  );
}

export function Component() {
  return <GlobalPermissions />;
}
