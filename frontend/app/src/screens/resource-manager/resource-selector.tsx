import { PropertyList } from "@/components/table/property-list";
import { Badge } from "@/components/ui/badge";
import { Card, CardWithBorder } from "@/components/ui/card";
import { constructPath } from "@/utils/fetch";
import { getObjectDetailsUrl2 } from "@/utils/objects";
import { Icon } from "@iconify-icon/react";
import { HTMLAttributes } from "react";
import { Link } from "react-router-dom";
import ResourcePoolUtilization from "./common/ResourcePoolUtilization";

export type ResourceProps = {
  id: string;
  display_label: string;
  kind: string;
  utilization: number;
  utilization_branches: number;
  utilization_default_branch: number;
};
interface ResourcePoolSelectorProps extends HTMLAttributes<HTMLDivElement> {
  resources: Array<ResourceProps>;
}

const ResourceSelector = ({ resources, className, ...props }: ResourcePoolSelectorProps) => {
  return (
    <Card className={className} {...props}>
      <CardWithBorder.Title className="bg-custom-white border-b">
        Resources <Badge>{resources.length}</Badge>
      </CardWithBorder.Title>

      <PropertyList
        className="block overflow-auto"
        valueClassName="w-full"
        labelClassName="truncate"
        properties={resources.map((resource) => ({
          name: (
            <Link
              to={getObjectDetailsUrl2(resource.kind, resource.id)}
              className="font-semibold underline"
            >
              {resource.display_label}
            </Link>
          ),
          value: (
            <div className="flex gap-2">
              <ResourcePoolUtilization
                utilizationOverall={resource.utilization}
                utilizationOtherBranches={resource.utilization_branches}
                utilizationDefaultBranch={resource.utilization_default_branch}
              />

              <Link
                to={constructPath(`resources/${resource.id}`)}
                className="flex items-center gap-1 text-nowrap hover:underline"
              >
                View <Icon icon="mdi:eye-outline" />
              </Link>
            </div>
          ),
        }))}
      />
    </Card>
  );
};

export default ResourceSelector;
