import { useQuery } from "@apollo/client";
import { GET_ROLE_MANAGEMENT_GROUPS } from "@/graphql/queries/role-management/getGroups";
import { Table } from "@/components/table/table";
import LoadingScreen from "../loading-screen/loading-screen";
import { ACCOUNT_GROUP_OBJECT, ACCOUNT_OBJECT } from "@/config/constants";
import ErrorScreen from "../errors/error-screen";
import { Pagination } from "@/components/ui/pagination";
import { GroupMembers } from "./group-member";

function Groups() {
  const { loading, data, error } = useQuery(GET_ROLE_MANAGEMENT_GROUPS);

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
    <div>
      <Table columns={columns} rows={rows ?? []} className="border-0" />

      <Pagination count={data && data[ACCOUNT_OBJECT]?.count} />
    </div>
  );
}

export function Component() {
  return <Groups />;
}
