import { useQuery } from "@apollo/client";
import { GET_ROLE_MANAGEMENT_ACCOUNTS } from "@/graphql/queries/role-management/getAccounts";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { ACCOUNT_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";

function Accounts() {
  const { loading, data, error } = useQuery(GET_ROLE_MANAGEMENT_ACCOUNTS);

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
      name: "status",
      label: "Status",
    },
  ];

  const rows =
    data &&
    data[ACCOUNT_OBJECT]?.edges.map((edge) => ({
      id: edge?.node?.id,
      values: {
        display_label: edge?.node?.display_label,
        description: edge?.node?.description?.value,
        account_type: edge?.node?.account_type?.value,
        status: edge?.node?.status?.value,
      },
    }));

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
  return <Accounts />;
}
