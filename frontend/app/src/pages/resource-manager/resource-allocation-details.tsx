import { Button } from "@/components/buttons/button-primitive";
import { Skeleton } from "@/components/skeleton";
import { Table } from "@/components/table/table";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Pagination } from "@/components/ui/pagination";
import { QSP } from "@/config/qsp";
import useQuery from "@/hooks/useQuery";
import { RESOURCE_POOL_ALLOCATED_KIND } from "@/screens/resource-manager/constants";
import { GET_RESOURCE_POOL_ALLOCATED } from "@/screens/resource-manager/graphql/resource-pool";
import { constructPath } from "@/utils/fetch";
import { getObjectDetailsUrl2 } from "@/utils/objects";
import { Icon } from "@iconify-icon/react";
import { Link, useParams } from "react-router-dom";

const ResourceAllocationDetailsPage = () => {
  const { resourcePoolId, resourceId } = useParams();
  const { data, loading } = useQuery(GET_RESOURCE_POOL_ALLOCATED, {
    variables: { poolId: resourcePoolId, resourceId: resourceId },
  });

  if (loading) return <ResourceAllocationPageSkeleton />;

  const getResourcePoolAllocatedData = data[RESOURCE_POOL_ALLOCATED_KIND];
  const resourcesAllocated = getResourcePoolAllocatedData.edges.map(({ node }: any) => ({
    values: { ...node },
    link: getObjectDetailsUrl2(node.kind, node.id, [{ name: QSP.BRANCH, value: node.branch }]),
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
    <Card className="flex flex-col ml-1 min-w-min max-w-fit sticky right-0 overflow-hidden max-h-full">
      <div className="pb-2 flex bg-custom-white items-center gap-1">
        <h3 className="font-semibold">Allocated resources</h3>
        <Badge>{totalOfResourcesAllocated}</Badge>

        <Link to={constructPath(`/resource-manager/${resourcePoolId}`)} className="ml-auto">
          <Button size="icon" variant="ghost">
            <Icon icon="mdi:close" className="text-xl" />
          </Button>
        </Link>
      </div>

      <div className="overflow-y-auto">
        <Table columns={columns} rows={resourcesAllocated} />
        <Pagination count={totalOfResourcesAllocated} className="pb-0" />
      </div>
    </Card>
  );
};

const ResourceAllocationPageSkeleton = () => {
  const { resourcePoolId } = useParams();

  return (
    <Card className="ml-1 w-full min-w-[450px] max-w-[606px] sticky right-0">
      <div className="pb-2 flex bg-custom-white items-center gap-1">
        <h3 className="font-semibold">Allocated resources</h3>
        <Badge>...</Badge>

        <Link to={constructPath(`/resource-manager/${resourcePoolId}`)} className="ml-auto">
          <Button size="icon" variant="ghost">
            <Icon icon="mdi:close" className="text-xl" />
          </Button>
        </Link>
      </div>

      <div className="space-y-1">
        <Skeleton className="h-7" />
        <Skeleton className="h-7" />
        <Skeleton className="h-7" />
        <Skeleton className="h-7" />
        <Skeleton className="h-7" />
        <Skeleton className="h-7" />
        <Skeleton className="h-7" />
        <Skeleton className="h-7" />
      </div>
    </Card>
  );
};

export function Component() {
  return <ResourceAllocationDetailsPage />;
}
