import { CardWithBorder } from "../../components/ui/card";
import { Icon } from "@iconify-icon/react";
import { Badge } from "../../components/ui/badge";
import { Link } from "react-router-dom";
import { getObjectDetailsUrl2 } from "../../utils/objects";
import ResourcePoolUtilization from "./common/ResourcePoolUtilization";
import { PropertyList } from "../../components/table/property-list";
import { constructPath } from "../../utils/fetch";

export type ResourceProps = {
  id: string;
  display_label: string;
  kind: string;
  utilization: number;
  utilization_branches: number;
  utilization_default_branch: number;
};
type ResourcePoolSelectorProps = {
  resources: Array<ResourceProps>;
};

const ResourceSelector = ({ resources }: ResourcePoolSelectorProps) => {
  return (
    <CardWithBorder className="divide-y">
      <CardWithBorder.Title className="bg-custom-white border-b">
        Resources <Badge>{resources.length}</Badge>
      </CardWithBorder.Title>

      <PropertyList
        valueClassName="w-full"
        properties={resources.map((resource) => ({
          name: (
            <Link
              to={getObjectDetailsUrl2(resource.kind, resource.id)}
              className="font-semibold underline">
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
                className="flex items-center gap-1 text-nowrap hover:underline">
                View <Icon icon="mdi:eye-outline" />
              </Link>
            </div>
          ),
        }))}
      />
    </CardWithBorder>
  );
};

export default ResourceSelector;
