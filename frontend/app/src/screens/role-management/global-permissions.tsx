import { useQuery } from "@apollo/client";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { GLOBAL_PERMISSION_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import { Pill } from "@/components/display/pill";
import { Icon } from "@iconify-icon/react";
import { BadgeCopy } from "@/components/ui/badge-copy";
import { GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS } from "@/graphql/queries/role-management/getGlobalPermissions";

function GlobalPermissions() {
  const { loading, data, error } = useQuery(GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS);

  const columns = [
    {
      name: "name",
      label: "Name",
    },
    {
      name: "action",
      label: "Action",
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
                <Icon icon={"mdi:lock-outline"} className="text-custom-blue-900" />
              </Pill>

              {edge?.node?.display_label}
            </div>
          ),
          description: edge?.node?.description?.value,
          roles: <Pill>{edge?.node?.roles?.count}</Pill>,
          identifier: <BadgeCopy value={edge?.node?.identifier?.value} />,
        },
      };
    });

  if (error) return <ErrorScreen message="An error occured while retrieving the accounts." />;

  if (loading) return <LoadingScreen message="Retrieving accounts..." />;

  return (
    <>
      <div>
        <Table columns={columns} rows={rows ?? []} className="border-0" />

        <Pagination count={data && data[GLOBAL_PERMISSION_OBJECT]?.count} />
      </div>
    </>
  );
}

export function Component() {
  return <GlobalPermissions />;
}
