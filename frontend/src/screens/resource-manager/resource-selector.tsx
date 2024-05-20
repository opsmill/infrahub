import { CardWithBorder } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Link } from "../../components/utils/link";

type ResourcePoolSelectorProps = {
  resources: Array<{
    id: string;
    display_label: string;
  }>;
};

const ResourceSelector = ({ resources }: ResourcePoolSelectorProps) => {
  return (
    <CardWithBorder className="divide-y">
      <CardWithBorder.Title>
        Select Resource pools <Badge variant="blue">{resources.length}</Badge>
      </CardWithBorder.Title>

      {resources.map(({ id, display_label }) => (
        <div key={id} className="p-2">
          {display_label} <Link to={"resources/" + id}>View</Link>
        </div>
      ))}
    </CardWithBorder>
  );
};

export default ResourceSelector;
