import Accordion from "../../../components/accordion";
import { BADGE_TYPES, Badge } from "../../../components/badge";

type Node = {
  id: string;
  action?: string;
  kind?: string;
}

type NodeProps = {
  node: Node,
}

const badgeTypes: { [key: string]: BADGE_TYPES } = {
  created: BADGE_TYPES.VALIDATE,
  updated: BADGE_TYPES.WARNING,
  deleted: BADGE_TYPES.CANCEL,
};

const getBadgeType = (action?: string) => {
  if (!action) return null;

  return badgeTypes[action];
};

export const DataDiffNode = (props: NodeProps) => {
  const { node } = props;
  console.log("node: ", node);

  const title = (
    <div>
      <Badge className="mr-2" type={getBadgeType(node?.action)}>
        {node.action?.toUpperCase()}
      </Badge>

      <Badge className="mr-2">
        {node.kind}
      </Badge>

      <span className="mr-2">
        {node.id}
      </span>
    </div>
  );

  return (
    <div className={"rounded-lg shadow p-6 m-6 bg-white"}>
      <Accordion title={title}>
        <div className="bg-white">
          <pre>
            {JSON.stringify(node, null, 2)}
          </pre>
        </div>
      </Accordion>
    </div>
  );
};