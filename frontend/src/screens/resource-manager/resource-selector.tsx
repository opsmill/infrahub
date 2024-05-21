import { CardWithBorder } from "../../components/ui/card";
import { Icon } from "@iconify-icon/react";
import { Badge } from "../../components/ui/badge";
import { Link, useParams } from "react-router-dom";
import { getObjectDetailsUrl2 } from "../../utils/objects";
import { classNames } from "../../utils/common";
import ResourcePoolUtilization from "./common/ResourcePoolUtilization";

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

      <div className="divide-y">
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
  const { resourceId } = useParams();

  return (
    <div
      className={classNames(
        "p-2 flex items-center gap-4 text-sm text-gray-600",
        resourceId === id && "bg-sky-50"
      )}>
      <Link to={getObjectDetailsUrl2(kind, id)} className="font-semibold underline">
        {display_label}
      </Link>

      <ResourcePoolUtilization
        utilizationOverall={utilization}
        utilizationDefaultBranch={utilization_default_branch}
      />

      <Link to={"resources/" + id} className="flex items-center gap-1 text-nowrap hover:underline">
        View allocations <Icon icon="mdi:arrow-right" />
      </Link>
    </div>
  );
};

export default ResourceSelector;
