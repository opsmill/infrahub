import { Icon } from "@iconify-icon/react";
import { Link, useParams } from "react-router";

import { QSP } from "@/config/qsp";

import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Skeleton } from "@/shared/components/skeleton";
import { Table } from "@/shared/components/table/table";
import { Badge } from "@/shared/components/ui/badge";
import { Card } from "@/shared/components/ui/card";
import { Pagination } from "@/shared/components/ui/pagination";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { GET_RESOURCE_POOL_ALLOCATED } from "@/entities/resource-manager/api/resource-pool";
import { RESOURCE_POOL_ALLOCATED_KIND } from "@/entities/resource-manager/constants";

const ResourceAllocationDetailsPage = () => {
  const { resourcePoolId, resourceId } = useParams();
  const { data, loading } = useQuery(GET_RESOURCE_POOL_ALLOCATED, {
    variables: { poolId: resourcePoolId, resourceId: resourceId },
  });

  if (loading) return <ResourceAllocationPageSkeleton />;

  const getResourcePoolAllocatedData = data[RESOURCE_POOL_ALLOCATED_KIND];
  const resourcesAllocated = getResourcePoolAllocatedData.edges.map(({ node }: any) => ({
    values: { ...node },
    link: getObjectDetailsUrl(node.kind, node.id, [{ name: QSP.BRANCH, value: node.branch }]),
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
    <Card className="sticky right-0 ml-1 flex max-h-full min-w-min max-w-fit flex-col overflow-hidden">
      <div className="flex items-center gap-1 bg-white pb-2">
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
    <Card className="sticky right-0 ml-1 w-full min-w-[450px] max-w-[606px]">
      <div className="flex items-center gap-1 bg-white pb-2">
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
