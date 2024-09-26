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
import { ReactNode } from "react";
import { Icon } from "@iconify-icon/react";
import { BadgeCopy } from "@/components/ui/badge-copy";

const icons: Record<string, ReactNode> = {
  [GLOBAL_PERMISSION_OBJECT]: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-custom-blue-500/20">
      <Icon icon={"mdi:lock-outline"} />
    </Pill>
  ),
  [OBJECT_PERMISSION_OBJECT]: (
    <Pill className="flex items-center justify-center w-6 h-6 bg-green-500/20">
      <Icon icon={"mdi:lock-check-outline"} />
    </Pill>
  ),
};

function Permissions() {
  const { loading, data, error } = useQuery(GET_ROLE_MANAGEMENT_PERMISSIONS);

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
      return {
        id: edge?.node?.id,
        values: {
          display_label: (
            <div className="flex items-center gap-2">
              {icons[edge?.node?.__typename]} {edge?.node?.display_label}
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
    <div>
      <Table columns={columns} rows={rows ?? []} className="border-0" />

      <Pagination count={data && data[ACCOUNT_OBJECT]?.count} />
    </div>
  );
}

export function Component() {
  return <Permissions />;
}
