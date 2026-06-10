import { Icon } from "@iconify-icon/react";
import { Card, CardContent, LinkButton } from "@infrahub/ui";
import { useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { Table } from "@/shared/components/table/table";
import { Badge } from "@/shared/components/ui/badge";
import { Pagination } from "@/shared/components/ui/pagination";
import { QSP } from "@/shared/config/qsp";
import usePagination from "@/shared/hooks/usePagination";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useGetResourceAllocated } from "@/entities/resource-manager/ui/queries/get-resource-allocated.query";

const ResourceAllocationDetailsPage = () => {
  const { resourcePoolId, resourceId } = useParams();
  const [{ limit, offset }] = usePagination();

  const { data, error, isPending } = useGetResourceAllocated({
    poolId: resourcePoolId!,
    resourceId: resourceId!,
    limit,
    offset,
  });

  if (isPending) return <ResourceAllocationPageSkeleton />;

  if (error) return <ErrorScreen message={error.message} />;

  const resourcesAllocated = data.nodes.map((node) => ({
    values: node,
    link: getObjectDetailsUrl(node.kind, node.id, [{ name: QSP.BRANCH, value: node.branch }]),
  }));
  const totalOfResourcesAllocated = data.count;

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
    <Card className="sticky right-0 ml-1 max-h-full min-w-min max-w-fit">
      <CardContent>
        <div className="flex items-center gap-1 pb-2">
          <h3 className="font-semibold">Allocated resources</h3>
          <Badge>{totalOfResourcesAllocated}</Badge>

          <LinkButton
            href={constructPath(`/resource-manager/${resourcePoolId}`)}
            size="xs"
            shape="circle"
            variant="ghost"
            className="ml-auto"
          >
            <Icon icon="mdi:close" className="text-xl" />
          </LinkButton>
        </div>

        <div className="overflow-y-auto">
          <Table columns={columns} rows={resourcesAllocated} />
          <Pagination count={totalOfResourcesAllocated} className="pb-0" />
        </div>
      </CardContent>
    </Card>
  );
};

const ResourceAllocationPageSkeleton = () => {
  const { resourcePoolId } = useParams();

  return (
    <Card className="sticky right-0 ml-1 w-full min-w-[450px] max-w-[606px]">
      <CardContent>
        <div className="flex items-center gap-1 pb-2">
          <h3 className="font-semibold">Allocated resources</h3>
          <Badge>...</Badge>

          <LinkButton
            href={constructPath(`/resource-manager/${resourcePoolId}`)}
            size="xs"
            shape="circle"
            variant="ghost"
            className="ml-auto"
          >
            <Icon icon="mdi:close" className="text-xl" />
          </LinkButton>
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
      </CardContent>
    </Card>
  );
};

export const Component = ResourceAllocationDetailsPage;
