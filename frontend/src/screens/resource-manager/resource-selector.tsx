import { CardWithBorder } from "../../components/ui/card";
import { Icon } from "@iconify-icon/react";
import ResourceUtilizationTooltipContent from "./resource-utilization-tooltip";
import MultipleProgressBar from "../../components/stats/multiple-progress-bar";
import { Badge } from "../../components/ui/badge";
import { Link } from "react-router-dom";
import { getObjectDetailsUrl2 } from "../../utils/objects";

type ResourceProps = {
  id: string;
  display_label: string;
  kind: string;
  utilization: number;
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

      <div className="px-2 divide-y">
        {resources.map((resource) => (
          <ResourcePoolOption key={resource.id} {...resource} />
        ))}
      </div>
    </CardWithBorder>
  );
};

const ResourcePoolOption = ({
  display_label,
  id,
  kind,
  utilization,
  utilization_default_branch,
}: ResourceProps) => {
  const utilization_branches = utilization - utilization_default_branch;

  return (
    <div className="p-2 flex items-center gap-4 text-sm">
      <Link to={getObjectDetailsUrl2(kind, id)} className="font-semibold underline">
        {display_label}
      </Link>

      <MultipleProgressBar
        className="h-3"
        elements={[
          {
            value: utilization_default_branch,
            tooltip: (
              <ResourceUtilizationTooltipContent
                value={utilization_default_branch}
                description="The overall utilization of the pool isolated to the default branch"
              />
            ),
          },
          {
            value: utilization_branches,
            tooltip: (
              <ResourceUtilizationTooltipContent
                value={utilization_branches}
                description="The utilization of the pool across all branches aside from the default one"
              />
            ),
          },
        ]}
      />

      <Link to={"resources/" + id} className="flex items-center gap-1 text-nowrap hover:underline">
        View allocations <Icon icon="mdi:arrow-right" />
      </Link>
    </div>
  );
};

export default ResourceSelector;
