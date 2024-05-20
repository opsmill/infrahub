import { CardWithBorder } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Link } from "../../components/utils/link";

type ResourcePoolSelectorProps = {
  resources: Array<{
    node: Record<string, any>;
    properties: Record<string, any>;
  }>;
};

const ResourceSelector = ({ resources }: ResourcePoolSelectorProps) => {
  return (
    <CardWithBorder className="divide-y">
      <CardWithBorder.Title>
        Select Resource pools <Badge variant="blue">{resources.length}</Badge>
      </CardWithBorder.Title>

      {resources.map(({ node }) => (
        <div key={node.id} className="p-2">
          {node.display_label} <Link to={"resources/" + node.id}>View</Link>
        </div>
      ))}
    </CardWithBorder>
  );
};

export default ResourceSelector;
