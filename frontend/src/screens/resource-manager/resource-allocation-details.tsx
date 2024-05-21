import { Link, useParams } from "react-router-dom";
import useQuery from "../../hooks/useQuery";
import { Spinner } from "../../components/ui/spinner";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Table } from "../../components/table/table";
import { GET_RESOURCE_POOL_ALLOCATED } from "./graphql/resource-pool";
import { RESOURCE_POOL_ALLOCATED_KIND } from "./constants";
import { Icon } from "@iconify-icon/react";
import { Button } from "../../components/buttons/button-primitive";
import { constructPath } from "../../utils/fetch";

const ResourceAllocationDetails = () => {
  const { resourcePoolId, resourceId } = useParams();
  const { data, loading } = useQuery(GET_RESOURCE_POOL_ALLOCATED, {
    variables: { poolId: resourcePoolId, resourceId: resourceId },
  });

  if (loading) return <Spinner />;

  const getResourcePoolAllocatedData = data[RESOURCE_POOL_ALLOCATED_KIND];
  const resourcesAllocated = getResourcePoolAllocatedData.edges.map(({ node }: any) => ({
    values: { ...node },
  }));
  const totalOfResourcesAllocated = getResourcePoolAllocatedData.count;

  const columns = [
    {
      name: "display_label",
      label: "Display label",
    },
    {
      name: "branch",
      label: "Branch",
    },
    {
      name: "identifier",
      label: "Identifier",
    },
    {
      name: "kind",
      label: "Kind",
    },
    {
      name: "id",
      label: "ID",
    },
  ];
  return (
    <Card>
      <div className="pb-2 flex bg-custom-white items-center gap-1">
        <h3 className="font-semibold">Allocated resources</h3>
        <Badge>{totalOfResourcesAllocated}</Badge>

        <Link to={constructPath(`/resource-manager/${resourcePoolId}`)} className="ml-auto">
          <Button size="icon" variant="ghost">
            <Icon icon="mdi:close" className="text-xl" />
          </Button>
        </Link>
      </div>

      <Table columns={columns} rows={resourcesAllocated} />
    </Card>
  );
};

export default ResourceAllocationDetails;
